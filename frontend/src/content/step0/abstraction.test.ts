// step0's abstraction ladder, checked against the things it makes claims about.
//
// The assertions live in ../abstraction/checks.ts, shared with step1. Read that file
// for what they catch and, more importantly, what they cannot: nothing here runs
// sklearn or torch, so no test can tell you the asserted defaults are TRUE. They were
// read from primary sources by hand on 2026-08-29 and each rung's `provenance`
// records whose word each claim is on.

import { readFileSync } from 'node:fs'

import { STEP0_ABSTRACTION } from './abstraction'
import { STEP0_SOURCES } from './source'
import { describeAbstraction } from '../abstraction/checks'

describeAbstraction(
  'step0',
  STEP0_ABSTRACTION,
  STEP0_SOURCES,
  readFileSync(new URL('./abstraction.mdx', import.meta.url), 'utf8'),
)
