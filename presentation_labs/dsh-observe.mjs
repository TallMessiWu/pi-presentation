// This teaching plugin only selects the common file tool and records completed reads.
// The packaged dsh file service and both stock executors run normally.
import { appendFileSync } from 'node:fs'
import { basename } from 'node:path'

export const name = 'presentation-observe-reads'
export const inject = ['tools']

export function apply(ctx, config) {
  ctx.on('agent/created', ({ agent }) => {
    agent.ctx.tools.restrict({ allow: ['read'] })
  }, { global: true })
  ctx.on('fs/observed', (target, observation) => {
    if (observation.kind === 'present') {
      appendFileSync(config.trace, JSON.stringify(basename(target.displayPath)) + '\n')
    }
  }, { global: true })
}
