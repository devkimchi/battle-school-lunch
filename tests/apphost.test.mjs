import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import test from 'node:test';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { createContext, SourceTextModule, SyntheticModule } from 'node:vm';
import ts from 'typescript';

const apphostPath = fileURLToPath(new URL('../apphost.mts', import.meta.url));
const rootDirectory = dirname(apphostPath);
const source = await readFile(apphostPath, 'utf8');
const apphostCode = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
}).outputText;

async function runAppHost({
  env = {},
  dotenv = {},
  envFileExists = true,
  hostConfiguration = {},
  publish = false,
} = {}) {
  const processEnvironment = { ...env };
  const configurationValues = new Map(Object.entries(hostConfiguration));
  const calls = [];
  const resources = new Map();
  const pending = [];
  const consoleOutput = [];

  function addResource(kind, name, args = []) {
    const resource = {
      kind,
      name,
      getEndpoint(endpoint) {
        return { resource: name, endpoint };
      },
      getOutput(output) {
        return { resource: name, output };
      },
      addProject(projectName) {
        return addResource('foundry-project', projectName);
      },
      addModelDeployment(modelName, model) {
        return addResource('foundry-model', modelName, [model]);
      },
      withProperties(callback) {
        pending.push(callback({
          skuCapacity: {
            async set(value) {
              calls.push({ resource: name, method: 'skuCapacity', args: [value] });
            },
          },
        }));
        return resource;
      },
      publishAsDockerFile(callback) {
        calls.push({ resource: name, method: 'publishAsDockerFile', args: [] });
        pending.push(callback(resource));
        return resource;
      },
      withEndpointCallback(endpoint, callback) {
        calls.push({ resource: name, method: 'withEndpointCallback', args: [endpoint] });
        pending.push(callback({
          targetPort: {
            async set(value) {
              calls.push({ resource: name, method: 'targetPort', args: [value] });
            },
          },
        }));
        return resource;
      },
    };

    for (const method of [
      'withFoundryRoleAssignments',
      'withParameter',
      'withUv',
      'withDockerfile',
      'withEnvironment',
      'withHttpHealthCheck',
      'withComputeEnvironment',
      'withAzureUserAssignedIdentity',
      'withReference',
      'waitFor',
      'withExternalHttpEndpoints',
    ]) {
      resource[method] = (...methodArgs) => {
        calls.push({ resource: name, method, args: methodArgs });
        return resource;
      };
    }

    resources.set(name, resource);
    calls.push({ resource: name, method: 'add', args: [kind, ...args] });
    return resource;
  }

  const builder = {
    getConfiguration() {
      return {
        async getSection(key) {
          calls.push({ method: 'getSection', args: [key] });
          return {
            value: {
              async get() {
                return configurationValues.has(key) ? configurationValues.get(key) : null;
              },
              async set(value) {
                calls.push({ method: 'setConfiguration', args: [key, value] });
                configurationValues.set(key, value);
              },
            },
          };
        },
      };
    },
    executionContext() {
      return {
        async isPublishMode() {
          return publish;
        },
        async isRunMode() {
          return !publish;
        },
      };
    },
    addAzureContainerAppEnvironment(name) {
      return addResource('container-app-environment', name);
    },
    addFoundry(name) {
      return addResource('foundry', name);
    },
    addAzureUserAssignedIdentity(name) {
      return addResource('identity', name);
    },
    addBicepTemplate(name, path) {
      return addResource('bicep', name, [path]);
    },
    addParameter(name, options) {
      return addResource('parameter', name, [options]);
    },
    addUvicornApp(name, path, entrypoint) {
      return addResource('uvicorn', name, [path, entrypoint]);
    },
    addViteApp(name, path) {
      return addResource('vite', name, [path]);
    },
    build() {
      return {
        async run() {
          calls.push({ method: 'run', args: [] });
        },
      };
    },
  };

  const modules = {
    'node:fs': {
      existsSync(path) {
        calls.push({ method: 'existsSync', args: [path] });
        return envFileExists && path === join(rootDirectory, '.env');
      },
      mkdirSync(path) {
        calls.push({ method: 'mkdirSync', args: [path] });
      },
      copyFileSync(from, to) {
        calls.push({ method: 'copyFileSync', args: [from, to] });
      },
    },
    'node:path': { join },
    'node:process': {
      loadEnvFile(path) {
        calls.push({ method: 'loadEnvFile', args: [path] });
        for (const [key, value] of Object.entries(dotenv)) {
          if (processEnvironment[key] === undefined) {
            processEnvironment[key] = value;
          }
        }
      },
    },
    'node:url': { fileURLToPath },
    './.aspire/modules/aspire.mjs': {
      FoundryModels: { OpenAI: { Gpt5Mini: 'gpt-5-mini' } },
      async createBuilder() {
        return builder;
      },
    },
  };

  const context = createContext({
    URL,
    process: { env: processEnvironment },
    console: {
      log: (...args) => consoleOutput.push(args),
      warn: (...args) => consoleOutput.push(args),
      error: (...args) => consoleOutput.push(args),
    },
  });
  const apphost = new SourceTextModule(apphostCode, {
    context,
    identifier: pathToFileURL(apphostPath).href,
    initializeImportMeta(meta) {
      meta.url = pathToFileURL(apphostPath).href;
    },
  });
  await apphost.link((specifier) => {
    const exports = modules[specifier];
    assert.ok(exports, `Unexpected import: ${specifier}`);
    return new SyntheticModule(Object.keys(exports), function () {
      for (const [key, value] of Object.entries(exports)) {
        this.setExport(key, value);
      }
    }, { context });
  });
  await apphost.evaluate();
  for (let index = 0; index < pending.length; index += 1) {
    await pending[index];
  }

  return { calls, configurationValues, consoleOutput, processEnvironment, resources };
}

test('loads .env from the AppHost directory and passes Azure settings to the host', async () => {
  const result = await runAppHost({
    dotenv: {
      NEIS_API_KEY: 'test-neis-secret',
      Azure__SubscriptionId: 'test-subscription',
      Azure__Location: 'test-region',
      Azure__TenantId: 'test-tenant',
      Azure__ResourceGroup: 'test-group',
    },
  });

  assert.deepEqual(
    result.calls.filter(({ method }) => method === 'loadEnvFile').map(({ args }) => args),
    [[join(rootDirectory, '.env')]],
  );
  assert.deepEqual(Object.fromEntries(result.configurationValues), {
    'Azure:SubscriptionId': 'test-subscription',
    'Azure:Location': 'test-region',
    'Azure:TenantId': 'test-tenant',
    'Azure:ResourceGroup': 'test-group',
  });
  const parameter = result.calls.find(({ resource, method }) => (
    resource === 'neis-api-key' && method === 'add'
  ));
  assert.equal(parameter.args[1].value, 'test-neis-secret');
  assert.equal(parameter.args[1].secret, true);
  assert.equal(JSON.stringify(result.consoleOutput).includes('test-neis-secret'), false);
});

test('preserves host settings and shell environment values over .env', async () => {
  const result = await runAppHost({
    env: { Azure__Location: 'shell-region', Azure__TenantId: 'shell-tenant' },
    dotenv: {
      Azure__Location: 'dotenv-region',
      Azure__TenantId: 'dotenv-tenant',
      Azure__SubscriptionId: 'dotenv-subscription',
      Azure__ResourceGroup: 'dotenv-group',
    },
    hostConfiguration: {
      'Azure:SubscriptionId': 'host-subscription',
      'Azure:ResourceGroup': '',
    },
  });

  assert.deepEqual(Object.fromEntries(result.configurationValues), {
    'Azure:SubscriptionId': 'host-subscription',
    'Azure:ResourceGroup': '',
    'Azure:Location': 'shell-region',
    'Azure:TenantId': 'shell-tenant',
  });
  assert.deepEqual(
    result.calls.filter(({ method }) => method === 'setConfiguration').map(({ args }) => args[0]),
    ['Azure:Location', 'Azure:TenantId'],
  );
});

test('leaves absent or empty Azure values unset when .env is missing', async () => {
  const result = await runAppHost({
    envFileExists: false,
    env: { Azure__SubscriptionId: '', Azure__Location: 'shell-region' },
    hostConfiguration: { 'Azure:TenantId': 'host-tenant' },
  });

  assert.equal(result.calls.some(({ method }) => method === 'loadEnvFile'), false);
  assert.deepEqual(Object.fromEntries(result.configurationValues), {
    'Azure:TenantId': 'host-tenant',
    'Azure:Location': 'shell-region',
  });
});

test('run mode retains the service graph without deployment-only identity resources', async () => {
  const result = await runAppHost();

  for (const name of ['aca', 'foundry', 'foundry-project', 'foundry-model', 'api', 'mcp', 'agent', 'web']) {
    assert.ok(result.resources.has(name), `${name} is missing`);
  }
  assert.equal(result.resources.has('agent-identity'), false);
  assert.equal(result.resources.has('agent-foundry-user-role'), false);
  assert.equal(result.calls.some(({ resource, method }) => (
    resource === 'agent' && method === 'withAzureUserAssignedIdentity'
  )), false);

  const dependencies = (resource, method) => result.calls
    .filter((call) => call.resource === resource && call.method === method)
    .map(({ args }) => args[0].name);
  assert.deepEqual(dependencies('agent', 'waitFor'), ['foundry-project', 'foundry-model', 'mcp']);
  assert.deepEqual(dependencies('agent', 'withReference'), ['foundry-project', 'foundry-model', 'mcp']);
  assert.deepEqual(dependencies('web', 'waitFor'), ['api', 'agent']);
  assert.deepEqual(dependencies('web', 'withReference'), ['api', 'agent']);
  assert.ok(result.calls.some(({ resource, method, args }) => (
    resource === 'foundry-model' && method === 'skuCapacity' && args[0] === 10
  )));
});

test('publish mode connects the actual identity outputs to the project-scoped role', async () => {
  const result = await runAppHost({ publish: true });

  const identity = result.resources.get('agent-identity');
  const role = result.resources.get('agent-foundry-user-role');
  assert.ok(identity);
  assert.ok(role);

  const parameters = Object.fromEntries(result.calls
    .filter(({ resource, method }) => resource === 'agent-foundry-user-role' && method === 'withParameter')
    .map(({ args }) => [args[0], args[1].value]));
  assert.deepEqual(parameters, {
    identityName: { resource: 'agent-identity', output: 'name' },
    identityPrincipalId: { resource: 'agent-identity', output: 'principalId' },
    foundryAccountName: { resource: 'foundry', output: 'name' },
    foundryProjectName: { resource: 'foundry-project', output: 'name' },
  });
  assert.ok(result.calls.some(({ resource, method, args }) => (
    resource === 'agent' && method === 'withAzureUserAssignedIdentity' && args[0] === identity
  )));
  assert.ok(result.calls.some(({ resource, method, args }) => (
    resource === 'agent' && method === 'waitFor' && args[0] === role
  )));
});

test('project role keeps its previous name-based GUID and uses the supplied principal', async () => {
  const bicep = await readFile(new URL('../infra/agent-foundry-user-role.bicep', import.meta.url), 'utf8');

  assert.match(bicep, /param identityName string/);
  assert.match(bicep, /param identityPrincipalId string/);
  assert.match(bicep, /53ca6127-db72-4b80-b1b0-d745d6d5456d/);
  assert.match(bicep, /name: guid\(foundryProject\.id, identityName, foundryUserRoleDefinitionId\)/);
  assert.match(bicep, /scope: foundryProject/);
  assert.match(bicep, /principalId: identityPrincipalId/);
  assert.doesNotMatch(bicep, /resource agentIdentity /);
});
