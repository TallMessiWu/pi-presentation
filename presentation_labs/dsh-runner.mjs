// node presentation_labs/dsh-runner.mjs 50
// Both official headless runs use temporary workspaces and a loopback-only Messages provider.
import assert from 'node:assert/strict'
import { spawn } from 'node:child_process'
import { randomBytes } from 'node:crypto'
import { once } from 'node:events'
import { copyFile, mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { createServer } from 'node:http'
import { createRequire } from 'node:module'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'

const require = createRequire(import.meta.url)
const cli = join(dirname(require.resolve('@deepseek-ai/dsh/package.json')), 'lib', 'bin.js')
const program = [
  "const manifest = await tools.read({ file_path: 'manifest.json' })",
  "const log = await tools.read({ file_path: JSON.parse(manifest.lines[0].text).log })",
  "inspect(log.lines.find(line => line.text.startsWith('FAIL ')).text)",
].join('\n')
const task = 'Read manifest.json, follow its log path and report only the first failed test name.'
const marker = 'INFO worker started'

function mockReply(body, mode) {
  const previous = body.messages.flatMap(message => Array.isArray(message.content)
    ? message.content.filter(block => block.type === 'tool_result') : [])
  const last = previous.at(-1)
  assert(!last?.is_error, 'Tool failed: ' + JSON.stringify(last?.content))
  const result = last?.content.map(block => block.text).join('\n') ?? ''
  if (previous.length === 0) {
    return mode === 'native'
      ? { type: 'tool_use', id: 'manifest', name: 'read', input: { file_path: 'manifest.json' } }
      : { type: 'tool_use', id: 'program', name: 'run_code', input: { code: program, description: 'Find the first failing CI test' } }
  }
  if (mode === 'native' && previous.length === 1) {
    const manifestLine = result.match(/^1: (\{.*\})$/m)
    assert(manifestLine, 'The native read result should contain the rendered manifest')
    return { type: 'tool_use', id: 'log', name: 'read', input: { file_path: JSON.parse(manifestLine[1]).log } }
  }
  const failed = result.match(/\bFAIL (test_[a-z_]+)/)
  assert(failed, 'The tool result must contain an actual failed test name')
  return { type: 'text', text: failed[1] }
}

function streamReply(res, model, block) {
  const isTool = block.type === 'tool_use'
  const usage = { input_tokens: 1, output_tokens: 1 } // Fixture counters, not a token measurement.
  const frames = [
    { type: 'message_start', message: { id: 'presentation-reply', type: 'message', role: 'assistant', model,
      content: [], stop_reason: null, stop_sequence: null, usage } },
    { type: 'content_block_start', index: 0, content_block: isTool
      ? { type: 'tool_use', id: block.id, name: block.name, input: {} } : { type: 'text', text: '' } },
    { type: 'content_block_delta', index: 0, delta: isTool
      ? { type: 'input_json_delta', partial_json: JSON.stringify(block.input) }
      : { type: 'text_delta', text: block.text } },
    { type: 'content_block_stop', index: 0 },
    { type: 'message_delta', delta: { stop_reason: isTool ? 'tool_use' : 'end_turn', stop_sequence: null }, usage },
    { type: 'message_stop' },
  ]
  res.writeHead(200, { 'content-type': 'text/event-stream' })
  res.end(frames.map(event => 'event: ' + event.type + '\ndata: ' + JSON.stringify(event) + '\n\n').join(''))
}

async function runMode(root, mode, logName, logText) {
  const home = join(root, mode, 'home')
  const workspace = join(root, mode, 'workspace')
  const trace = join(root, mode, 'reads.jsonl')
  const patch = join(root, mode, 'demo.yml')
  await mkdir(home, { recursive: true })
  await mkdir(workspace)
  await copyFile(new URL('./dsh-observe.mjs', import.meta.url), join(root, mode, 'dsh-observe.mjs'))
  await writeFile(join(workspace, 'manifest.json'), JSON.stringify({ log: logName }) + '\n')
  await writeFile(join(workspace, logName), logText)
  await writeFile(patch, [
    '- id: session-title-llm', '  disabled: true',
    '- id: tool-executor-native', '  disabled: ' + (mode === 'ptc'),
    '- id: tool-executor-ptc', '  disabled: ' + (mode !== 'ptc'),
    '- insert:', '    - id: presentation-observe', '      name: "./dsh-observe.mjs"',
    '      config:', '        trace: ' + JSON.stringify(trace),
  ].join('\n') + '\n')
  const requests = []
  let providerError
  const server = createServer(async (req, res) => {
    try {
      assert(req.method === 'POST' && req.url.split('?')[0].endsWith('/v1/messages'), 'Unexpected mock endpoint ' + req.url)
      const chunks = []
      for await (const chunk of req) chunks.push(chunk)
      const body = JSON.parse(Buffer.concat(chunks).toString())
      assert(requests.length < 4, 'Unexpected additional LLM request')
      requests.push(body)
      streamReply(res, body.model, mockReply(body, mode))
    } catch (error) {
      providerError ??= error
      res.writeHead(400, { 'content-type': 'application/json' })
      res.end(JSON.stringify({ type: 'error', error: { type: 'invalid_request_error', message: error.message } }))
    }
  })
  server.listen(0, '127.0.0.1')
  await once(server, 'listening')
  try {
    const env = Object.fromEntries(Object.entries(process.env).filter(([key]) =>
      /^(PATH|HOME|USERPROFILE|LOCALAPPDATA|APPDATA|SYSTEMROOT|COMSPEC|PATHEXT|TEMP|TMP|TMPDIR|LANG|LC_ALL)$/i.test(key)))
    Object.assign(env, { DSH_HOME: home, DSH_TELEMETRY_DISABLED: '1', DEEPSEEK_API_KEY: 'offline-demo',
      DEEPSEEK_BASE_URL: 'http://127.0.0.1:' + server.address().port })
    const args = [cli, '--profile', 'headless', '--patch', patch,
      '--permission-mode', 'read-only', '--approval-policy', 'never', '--json', task]
    const child = spawn(process.execPath, args, { cwd: workspace, env, stdio: ['ignore', 'pipe', 'pipe'] })
    let stdout = '', stderr = ''
    child.stdout.on('data', chunk => { stdout += chunk })
    child.stderr.on('data', chunk => { stderr += chunk })
    const timer = setTimeout(() => child.kill(), 90000)
    let exit
    try { [exit] = await once(child, 'close') } finally { clearTimeout(timer) }
    if (providerError) throw providerError
    if (exit !== 0) throw new Error('dsh (' + mode + ') exit ' + exit + '\n' + stderr.slice(-3000) + '\n' + stdout.slice(-1200))
    const reads = (await readFile(trace, 'utf8')).trim().split('\n').map(line => JSON.parse(line))
    const lastResult = requests.at(-1).messages.at(-1).content.find(block => block.type === 'tool_result')
    const last_tool_result = lastResult.content.map(block => block.text).join('\n')
    const finalLine = stdout.trim().split(/\r?\n/).find(line => line.startsWith('{"type":"final",'))
    assert(finalLine, 'Expected a final event from the headless session')
    const final = JSON.parse(finalLine)
    assert.equal(final.reason.kind, 'completed')
    const answer = final.text
    assert.equal(answer, mockReply(requests.at(-1), mode).text)
    assert.deepEqual(reads, ['manifest.json', logName])
    assert.equal(requests.length, mode === 'native' ? 3 : 2)
    assert.deepEqual(requests[0].tools.map(t => t.name), [mode === 'native' ? 'read' : 'run_code'])
    return { answer, reads, requests, last_tool_result, result_chars: [...last_tool_result].length,
      log_marker_visible: last_tool_result.includes(marker) }
  } finally {
    server.closeAllConnections()
    await new Promise(resolve => server.close(resolve))
  }
}

const extra_info = Number(process.argv[2] ?? 0)
if (!Number.isInteger(extra_info) || extra_info < 0 || extra_info > 200) throw new Error('extra INFO count must be 0–200')
const root = await mkdtemp(join(tmpdir(), 'dsh-notebook-'))
try {
  const logName = 'ci-' + randomBytes(3).toString('hex') + '.log'
  const logText = [marker, ...Array.from({ length: extra_info }, (_, i) => 'INFO routine message ' + (i + 1)),
    'FAIL test_invoice_total', 'INFO build completed'].join('\n') + '\n'
  const native = await runMode(root, 'native', logName, logText)
  const ptc = await runMode(root, 'ptc', logName, logText)
  assert.equal(native.answer, ptc.answer)
  assert(native.log_marker_visible && !ptc.log_marker_visible)
  console.log(JSON.stringify({ extra_info, native, ptc }))
} finally {
  await rm(root, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 })
}
