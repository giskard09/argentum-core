// Run (Node >= 22.6, no install needed):
//   node --experimental-strip-types --test test/actionRef.test.ts
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { computeActionRef, OutOfProfileDomainError } from "../src/actionRef.ts";

const conformance = (name: string) =>
  JSON.parse(readFileSync(new URL(`../../conformance/${name}`, import.meta.url), "utf8"));

const BASE = {
  agent_id: "did:aeoess:example",
  action_type: "trail.anchor",
  scope: "mycelium:av-neg",
  timestamp: "2026-05-24T10:30:00.000Z",
};

test("baseline fixture: every (preimage, action_ref) pair reproduces", () => {
  const fx = conformance("action-ref-v1-baseline.fixture.json");
  const pairs: { id: string; preimage: Record<string, string>; action_ref: string }[] = [];
  const collect = (v: any, id: string) => {
    if (v && v.preimage && v.action_ref) pairs.push({ id, preimage: v.preimage, action_ref: v.action_ref });
    for (const sub of v?.vectors ?? []) collect(sub, `${id}/${sub.id ?? pairs.length}`);
  };
  for (const v of fx.vectors) collect(v, v.id);
  assert.ok(pairs.length >= 3, `expected at least 3 pairs, got ${pairs.length}`);
  for (const { id, preimage: p, action_ref } of pairs) {
    assert.equal(computeActionRef(p.agent_id, p.action_type, p.scope, p.timestamp), action_ref, id);
  }
});

test("known baseline value", () => {
  assert.equal(
    computeActionRef("giskard-self", "trail.anchor", "mycelium:baseline", "2026-05-23T00:00:00.000Z"),
    "f4ebda732e3c063bdd8547c734e4956f009bbed7f557cb949f7c8033e8c42d1d",
  );
});

test("domain-negative fixture: every vector is refused, on the declared field", () => {
  const fx = conformance("action-ref-v1-domain-negative/action-ref-v1-domain-negative.fixture.json");
  assert.equal(fx.vectors.length, 10);
  for (const v of fx.vectors) {
    const p = v.preimage;
    assert.equal(v.expect_valid, false, v.id);
    assert.throws(
      () => computeActionRef(p.agent_id, p.action_type, p.scope, p.timestamp),
      (e: unknown) => e instanceof OutOfProfileDomainError && e.field === v.expect_error_field,
      v.id,
    );
  }
});

test("timestamps that are not real instants are refused", () => {
  for (const ts of [
    "2026-02-30T10:30:00.000Z",
    "2026-05-24T25:99:99.000Z",
    "0000-05-24T10:30:00.000Z",
    "2026-05-24T10:30:60.000Z",
    "2023-02-29T00:00:00.000Z",
    "2026-13-01T00:00:00.000Z",
    "2026-04-31T00:00:00.000Z",
  ]) {
    assert.throws(
      () => computeActionRef(BASE.agent_id, BASE.action_type, BASE.scope, ts),
      (e: unknown) => e instanceof OutOfProfileDomainError && e.field === "timestamp",
      ts,
    );
  }
});

test("real calendar edge cases are accepted", () => {
  for (const ts of ["2024-02-29T23:59:59.999Z", "2000-02-29T00:00:00.000Z", "0001-01-01T00:00:00.000Z"]) {
    assert.match(computeActionRef(BASE.agent_id, BASE.action_type, BASE.scope, ts), /^[0-9a-f]{64}$/, ts);
  }
});

test("empty scope and non-string inputs are refused", () => {
  assert.throws(() => computeActionRef(BASE.agent_id, BASE.action_type, "", BASE.timestamp), OutOfProfileDomainError);
  assert.throws(
    () => computeActionRef(BASE.agent_id, BASE.action_type, BASE.scope, 1779494400 as unknown as string),
    OutOfProfileDomainError,
  );
});

test("the legacy colon construction does not equal v1", () => {
  const legacy = "3ad733678e731d4cb3f11bce1f4906e764b9e517be93abb231f4dc7a55f3b08c";
  assert.notEqual(
    computeActionRef("pioneer-agent-001", "agent_trail", "giskard-oasis", "2026-05-05T14:36:50.000Z"),
    legacy,
  );
});
