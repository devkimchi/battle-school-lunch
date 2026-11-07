// Aspire TypeScript AppHost
// For more information, see: https://aspire.dev

import { copyFileSync, existsSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';
import { loadEnvFile } from 'node:process';
import { fileURLToPath } from 'node:url';
import { FoundryModels, createBuilder } from './.aspire/modules/aspire.mjs';

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

const foundry = await builder.addFoundry('foundry');
const foundryProject = await foundry.addProject('foundry-project');
const foundryModel = await foundryProject.addModelDeployment(
  'foundry-model',
  FoundryModels.OpenAI.Gpt5Mini,
);
await foundryModel.withProperties(async (deployment) => {
  await deployment.skuCapacity.set(10);
});

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
  .withReference(foundryProject)
  .withReference(foundryModel)
  .withReference(mcp)
  .waitFor(foundryProject)
  .waitFor(foundryModel)
  .waitFor(mcp)
  .withHttpHealthCheck({ path: '/health' })
  .withComputeEnvironment(aca);

if (await builder.executionContext().isPublishMode()) {
  const agentIdentity = await builder.addAzureUserAssignedIdentity('agent-identity');
  const agentFoundryRoleAssignment = await builder
    .addBicepTemplate('agent-foundry-user-role', './infra/agent-foundry-user-role.bicep')
    .withParameter('identityName', { value: agentIdentity.getOutput('name') })
    .withParameter('identityPrincipalId', { value: agentIdentity.getOutput('principalId') })
    .withParameter('foundryAccountName', { value: foundry.getOutput('name') })
    .withParameter('foundryProjectName', { value: foundryProject.getOutput('name') });

  // Foundry references grant their account roles to the attached identity.
  await agent.withAzureUserAssignedIdentity(agentIdentity).waitFor(agentFoundryRoleAssignment);
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
