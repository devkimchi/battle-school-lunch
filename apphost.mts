// Aspire TypeScript AppHost
// For more information, see: https://aspire.dev

import { existsSync } from 'node:fs';
import { loadEnvFile } from 'node:process';
import { FoundryModels, FoundryRole, createBuilder } from './.aspire/modules/aspire.mjs';

if (existsSync('.env')) {
  loadEnvFile('.env');
}

const builder = await createBuilder();

const aca = await builder.addAzureContainerAppEnvironment('aca');

const foundry = await builder.addFoundry('foundry');
const foundryProject = await foundry.addProject('foundry-project');
const foundryModel = await foundryProject.addModelDeployment(
  'foundry-model',
  FoundryModels.OpenAI.Gpt5Mini,
);

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

await agent.withFoundryRoleAssignments(foundry, [FoundryRole.CognitiveServicesOpenAIUser]);

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
