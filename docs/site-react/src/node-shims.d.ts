declare module "node:assert/strict" {
  const assert: {
    equal(actual: unknown, expected: unknown): void;
    deepEqual(actual: unknown, expected: unknown): void;
  };
  export default assert;
}

declare module "node:test" {
  export default function test(name: string, callback: () => void): void;
}
