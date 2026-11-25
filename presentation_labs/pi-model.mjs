// Offline DeepSeek transport for the lab. pi itself still builds every request,
// runs its file tools, appends the results, and decides whether to iterate.
import { readFile, rename, stat, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { setTimeout as sleep } from 'node:timers/promises';

const traceDir = process.env.PI_LAB_TRACE_DIR;
const endpoint = 'https://api.deepseek.com/chat/completions';
const firstRead = 'lab-read';
const edit = 'lab-edit';
const reread = 'lab-reread';
let round = 0;

function call(name, id, args) {
  return { role: 'assistant', tool_calls: [
    { index: 0, id, type: 'function', function: { name, arguments: JSON.stringify(args) } },
  ] };
}

function readConfig(id) {
  return call('read', id, { path: 'config.txt', offset: null, limit: null });
}

function chooseReply(last) {
  if (last.role === 'user') return readConfig(firstRead);
  if (last.role !== 'tool') throw new Error('Expected a real tool receipt from pi.');
  switch (last.tool_call_id) {
    case firstRead:
      return call('edit', edit, { path: 'config.txt', edits: [{ oldText: 'DEBUG', newText: 'RELEASE' }] });
    case edit:
      if (last.content.includes('Successfully replaced')) return { role: 'assistant', content: 'DONE' };
      if (last.content.includes('Could not find')) return readConfig(reread);
      throw new Error('Unexpected pi edit receipt: ' + last.content);
    case reread:
      return { role: 'assistant', content: '已重新读取，保留当前文件。' };
    default:
      throw new Error('Unexpected tool call id: ' + last.tool_call_id);
  }
}

async function pauseAfterRead() {
  // Signal only after the request snapshot has been fully written. The Python
  // caller can now change the real file after read and before pi receives edit.
  await writeFile(join(traceDir, 'paused'), '');
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline) {
    try {
      await stat(join(traceDir, 'continue'));
      return;
    } catch (error) {
      if (error.code !== 'ENOENT') throw error;
    }
    await sleep(25);
  }
  throw new Error('The Notebook did not release the paused pi experiment.');
}

globalThis.fetch = async (input, init) => {
  const request = new Request(input, init);
  if (request.method !== 'POST' || request.url !== endpoint) {
    throw new Error('Unexpected request from the offline pi experiment: ' + request.url);
  }
  const body = await request.json();
  const last = body.messages.at(-1);
  const index = ++round;
  if (index > 4) throw new Error('The offline scenario exceeded four model requests.');
  const reply = chooseReply(last);
  const diskAtRequest = await readFile('config.txt', 'utf8');
  const record = { request: body, model_reply: reply, disk_at_request: diskAtRequest };
  const file = join(traceDir, `round-${index}.json`);
  await writeFile(file + '.tmp', JSON.stringify(record));
  await rename(file + '.tmp', file);
  if (last.role === 'tool' && last.tool_call_id === firstRead) await pauseAfterRead();

  const choice = (delta, finish_reason) => 'data: ' + JSON.stringify({
    id: `chatcmpl-lab-${index}`, object: 'chat.completion.chunk',
    created: 0, model: body.model, choices: [{ index: 0, delta, finish_reason }],
  }) + '\n\n';
  return new Response(
    choice(reply, null) + choice({}, reply.tool_calls ? 'tool_calls' : 'stop') + 'data: [DONE]\n\n',
    { headers: { 'Content-Type': 'text/event-stream' } },
  );
};
