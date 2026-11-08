// Aspire TypeScript AppHost
// For more information, see: https://aspire.dev

import { copyFileSync, existsSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { loadEnvFile } from 'node:process';
import { fileURLToPath } from 'node:url';
import { createBuilder } from './.aspire/modules/aspire.mjs';

const rootDirectory = fileURLToPath(new URL('.', import.meta.url));
const envFile = join(rootDirectory, '.env');
if (existsSync(envFile)) {
  loadEnvFile(envFile);
}

const generatedAgentDirectory = join(rootDirectory, 'src', 'agent', '.generated');
mkdirSync(generatedAgentDirectory, { recursive: true });
copyFileSync(
  join(rootDirectory, 'EVALUATION-RUBRIC.md'),
  join(generatedAgentDirectory, 'EVALUATION-RUBRIC.md'),
);

const builder = await createBuilder();

const configuration = builder.getConfiguration();
const copilotModelSection = await configuration.getSection('Parameters:copilot-model');
const copilotModelValue = (await copilotModelSection.value.get())
  ?? process.env.COPILOT_MODEL
  ?? 'auto';
const copilotModel = await builder.addParameter('copilot-model', {
  value: copilotModelValue,
});

for (const name of ['SubscriptionId', 'Location', 'TenantId', 'ResourceGroup']) {
  const value = process.env[`Azure__${name}`];
  if (value) {
    const section = await configuration.getSection(`Azure:${name}`);
    if ((await section.value.get()) === null) {
      await section.value.set(value);
    }
  }
}

const aca = await builder.addAzureContainerAppEnvironment('aca');

const neisApiKey = await builder.addParameter('neis-api-key', {
  value: process.env.NEIS_API_KEY,
  secret: true,
});

const api = await builder
  .addUvicornApp('api', './src/api', 'app.main:app')
  .withUv()
  .publishAsDockerFile(async (container) => {
    await container
      .withDockerfile('./src', { dockerfilePath: 'api/Dockerfile' })
      .withEndpointCallback('http', async (endpoint) => {
        await endpoint.targetPort.set(8000);
      });
  })
  .withEnvironment('NEIS_API_KEY', neisApiKey)
  .withHttpHealthCheck({ path: '/api/health' })
  .withComputeEnvironment(aca);

const apiEndpoint = api.getEndpoint('http');

const mcp = await builder
  .addUvicornApp('mcp', './src/mcp', 'app.main:app')
  .withUv()
  .publishAsDockerFile(async (container) => {
    await container
      .withDockerfile('./src', { dockerfilePath: 'mcp/Dockerfile' })
      .withEndpointCallback('http', async (endpoint) => {
        await endpoint.targetPort.set(8000);
      });
  })
  .withEnvironment('NEIS_API_KEY', neisApiKey)
  .withHttpHealthCheck({ path: '/health' })
  .withComputeEnvironment(aca);

const mcpEndpoint = mcp.getEndpoint('http');

const isPublishMode = await builder.executionContext().isPublishMode();
const agent = await builder
  .addUvicornApp('agent', './src/agent', 'app.main:app')
  .withUv()
  .publishAsDockerFile(async (container) => {
    await container
      .withDockerfile('./src', { dockerfilePath: 'agent/Dockerfile' })
      .withEndpointCallback('http', async (endpoint) => {
        await endpoint.targetPort.set(8000);
      });
  })
  .withEnvironment('MCP_URL', mcpEndpoint)
  .withReference(mcp)
  .waitFor(mcp)
  .withEnvironment('COPILOT_MODEL', copilotModel)
  .withHttpHealthCheck({ path: '/health' })
  .withComputeEnvironment(aca);

if (isPublishMode) {
  const copilotGithubToken = await builder.addParameter('copilot-github-token', {
    secret: true,
  });
  await agent
    .withEnvironment('COPILOT_AUTH_MODE', 'pat')
    .withEnvironment('COPILOT_GITHUB_TOKEN', copilotGithubToken);
} else {
  await agent.withEnvironment('COPILOT_AUTH_MODE', 'local');
}

const agentEndpoint = agent.getEndpoint('http');

await builder
  .addViteApp('web', './src/web')
  .withEnvironment('API_URL', apiEndpoint)
  .withEnvironment('API_UPSTREAM', apiEndpoint)
  .withEnvironment('AGENT_URL', agentEndpoint)
  .withEnvironment('AGENT_UPSTREAM', agentEndpoint)
  .withReference(api)
  .withReference(agent)
  .waitFor(api)
  .waitFor(agent)
  .publishAsDockerFile(async (container) => {
    await container.withEndpointCallback('http', async (endpoint) => {
      await endpoint.targetPort.set(8080);
    });
  })
  .withComputeEnvironment(aca)
  .withExternalHttpEndpoints();

await builder.build().run();
