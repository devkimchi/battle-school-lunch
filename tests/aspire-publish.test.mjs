import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { mkdtemp, readFile, readdir, rm, rmdir, writeFile } from 'node:fs/promises';
import { homedir, tmpdir } from 'node:os';
import { basename, dirname, join } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';

const execFileAsync = promisify(execFile);
const rootDirectory = fileURLToPath(new URL('../', import.meta.url));
const fakeSecret = 'apphost-publish-test-secret';
const openAiUserRole = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd';

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

test('Azure publication preserves identity, roles, endpoints, and secret boundaries', {
  timeout: 180_000,
}, async (t) => {
  const testDirectory = await mkdtemp(join(tmpdir(), 'aspire-apphost-test-'));
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
        NEIS_API_KEY: fakeSecret,
        Parameters__neis_api_key: fakeSecret,
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
  const [main, identity, projectRole, accountRole, foundry, agent, api, mcp, web] = await Promise.all([
    readArtifact('main.bicep'),
    readArtifact('agent-identity', 'agent-identity.bicep'),
    readArtifact('agent-foundry-user-role', 'agent-foundry-user-role.bicep'),
    readArtifact('agent-roles-foundry', 'agent-roles-foundry.bicep'),
    readArtifact('foundry', 'foundry.bicep'),
    readArtifact('agent', 'agent.bicep'),
    readArtifact('api', 'api.bicep'),
    readArtifact('mcp', 'mcp.bicep'),
    readArtifact('web', 'web.bicep'),
  ]);

  for (const expression of [
    'identityName: agent_identity.outputs.name',
    'identityPrincipalId: agent_identity.outputs.principalId',
    'foundryAccountName: foundry.outputs.name',
    'foundryProjectName: foundry_project.outputs.name',
    'principalId: agent_identity.outputs.principalId',
  ]) {
    assert.ok(main.includes(expression), `Missing identity dependency: ${expression}`);
  }
  assert.ok(identity.includes('output name string = agent_identity.name'));
  assert.ok(identity.includes('output principalId string = agent_identity.properties.principalId'));
  assert.ok(projectRole.includes('53ca6127-db72-4b80-b1b0-d745d6d5456d'));
  assert.ok(projectRole.includes('scope: foundryProject'));
  assert.ok(projectRole.includes('name: guid(foundryProject.id, identityName, foundryUserRoleDefinitionId)'));
  assert.ok(projectRole.includes('principalId: identityPrincipalId'));
  assert.ok(accountRole.includes(openAiUserRole));
  assert.ok(accountRole.includes('scope: foundry'));
  assert.ok(foundry.includes("name: 'gpt-5-mini'"));
  assert.ok(foundry.includes('capacity: 10'));

  assert.ok(agent.includes("type: 'UserAssigned'"));
  assert.ok(agent.includes("'${agent_identity_outputs_id}'"));
  assert.match(agent, /name: 'AZURE_CLIENT_ID'\s+value: agent_identity_outputs_clientid/);
  assert.match(agent, /name: 'AZURE_TOKEN_CREDENTIALS'\s+value: 'ManagedIdentityCredential'/);
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
    assert.equal(contents.includes(fakeSecret), false, 'A secret was written to a published artifact.');
    if (contents.includes(openAiUserRole)) {
      roleFiles.push(path);
    }
  }
  assert.deepEqual(roleFiles, [join(output, 'agent-roles-foundry', 'agent-roles-foundry.bicep')]);
});
