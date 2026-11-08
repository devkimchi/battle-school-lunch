import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { mkdtemp, readFile, readdir, rm, rmdir, writeFile } from 'node:fs/promises';
import { homedir } from 'node:os';
import { basename, dirname, join } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';

const execFileAsync = promisify(execFile);
const rootDirectory = fileURLToPath(new URL('../', import.meta.url));
const fakeNeisSecret = 'apphost-publish-neis-secret';
const fakeCopilotToken = 'apphost-publish-copilot-token';

async function listFilesIfExists(directory) {
  try {
    return await listFiles(directory);
  } catch (error) {
    if (error.code === 'ENOENT') {
      return [];
    }
    throw error;
  }
}

async function readEnvironmentStates(aspireHome) {
  const states = new Map();
  for (const path of await listFilesIfExists(join(aspireHome, 'deployments'))) {
    if (basename(path) === 'apphost-test.json') {
      states.set(path, await readFile(path, 'utf8'));
    }
  }
  return states;
}

async function restoreEnvironmentStates(aspireHome, originalStates) {
  for (const [path, contents] of await readEnvironmentStates(aspireHome)) {
    if (!originalStates.has(path)) {
      await rm(path, { force: true });
      await rmdir(dirname(path)).catch(() => {});
    } else if (originalStates.get(path) !== contents) {
      await writeFile(path, originalStates.get(path), 'utf8');
    }
  }
}

async function listFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = await Promise.all(entries.map(async (entry) => {
    const path = join(directory, entry.name);
    return entry.isDirectory() ? listFiles(path) : [path];
  }));
  return files.flat();
}

test('Azure publication uses Copilot PAT securely and preserves endpoint boundaries', {
  timeout: 180_000,
}, async (t) => {
  const testDirectory = await mkdtemp(join(rootDirectory, '.aspire-publish-test-'));
  const output = join(testDirectory, 'output');
  const aspireHome = join(testDirectory, 'aspire-home');
  const userAspireHome = process.env.ASPIRE_HOME || join(homedir(), '.aspire');
  const userStatesBefore = await readEnvironmentStates(userAspireHome);
  // Aspire on Linux ignores ASPIRE_HOME for deployment state, so restore the test environment's user state.
  t.after(async () => {
    await restoreEnvironmentStates(userAspireHome, userStatesBefore);
    await rm(testDirectory, { recursive: true, force: true });
  });

  try {
    await execFileAsync('aspire', [
      'publish',
      '--apphost', rootDirectory,
      '--no-build',
      '--environment', 'apphost-test',
      '--output-path', output,
      '--non-interactive',
      '--nologo',
    ], {
      cwd: rootDirectory,
      env: {
        ...process.env,
        ASPIRE_HOME: aspireHome,
        NEIS_API_KEY: fakeNeisSecret,
        Parameters__neis_api_key: fakeNeisSecret,
        Parameters__copilot_github_token: fakeCopilotToken,
        Parameters__copilot_model: 'auto',
        Azure__SubscriptionId: '00000000-0000-0000-0000-000000000001',
        Azure__TenantId: '00000000-0000-0000-0000-000000000002',
        Azure__Location: 'koreacentral',
        Azure__ResourceGroup: 'rg-aspire-artifact-check',
      },
      timeout: 150_000,
    });
  } catch (error) {
    throw new Error(`Aspire publish failed (${error.code ?? 'unknown error'}); run npm run build first.`);
  }

  const readArtifact = (...path) => readFile(join(output, ...path), 'utf8');
  const [main, agent, api, mcp, web] = await Promise.all([
    readArtifact('main.bicep'),
    readArtifact('agent', 'agent.bicep'),
    readArtifact('api', 'api.bicep'),
    readArtifact('mcp', 'mcp.bicep'),
    readArtifact('web', 'web.bicep'),
  ]);

  assert.doesNotMatch(main, /foundry|agent-identity|roleAssignment/i);
  assert.match(agent, /param copilot_model_value string/);
  assert.match(agent, /@secure\(\)\s+param copilot_github_token_value string/);
  assert.match(agent, /name: 'COPILOT_AUTH_MODE'\s+value: 'pat'/);
  assert.match(agent, /name: 'COPILOT_MODEL'\s+value: copilot_model_value/);
  assert.match(agent, /name: 'COPILOT_GITHUB_TOKEN'/);
  assert.doesNotMatch(agent, /AZURE_CLIENT_ID|AZURE_TOKEN_CREDENTIALS/);
  assert.ok(agent.includes("value: 'https://mcp.internal."));
  for (const internal of [api, mcp, agent]) {
    assert.match(internal, /ingress:\s*\{\s*external: false/);
  }
  assert.match(web, /ingress:\s*\{\s*external: true\s+targetPort: 8080/);
  assert.ok(web.includes("value: 'https://api.internal."));
  assert.ok(web.includes("value: 'https://agent.internal."));

  const roleFiles = [];
  for (const path of await listFiles(output)) {
    const contents = await readFile(path);
    assert.equal(contents.includes(fakeNeisSecret), false, 'The NEIS secret was written to a published artifact.');
    assert.equal(contents.includes(fakeCopilotToken), false, 'The Copilot token was written to a published artifact.');
    assert.doesNotMatch(contents.toString('utf8'), /foundry|agent-identity|agent-roles/i);
    if (/foundry|agent-identity|agent-roles/i.test(path)) {
      roleFiles.push(path);
    }
  }
  assert.deepEqual(roleFiles, []);

  for (const service of [api, mcp, web]) {
    assert.doesNotMatch(service, /COPILOT_GITHUB_TOKEN|apphost-publish-copilot-token/);
  }
});
