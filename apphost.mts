// Aspire TypeScript AppHost
// For more information, see: https://aspire.dev

import { existsSync } from 'node:fs';
import { loadEnvFile } from 'node:process';
import { createBuilder } from './.aspire/modules/aspire.mjs';

if (existsSync('.env')) {
  loadEnvFile('.env');
}

const builder = await createBuilder();

await builder.addAzureContainerAppEnvironment('aca');

const neisApiKey = await builder.addParameter('neis-api-key', {
  value: process.env.NEIS_API_KEY,
  secret: true,
});

const foundryProjectEndpoint = await builder.addParameter('foundry-project-endpoint', {
  value: process.env.FOUNDRY_PROJECT_ENDPOINT,
});

const foundryModelDeploymentName = await builder.addParameter('foundry-model-deployment-name', {
  value: process.env.FOUNDRY_MODEL_DEPLOYMENT_NAME,
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
  .withHttpHealthCheck({ path: '/api/health' });

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
  .withHttpHealthCheck({ path: '/health' });

const mcpEndpoint = mcp.getEndpoint('http');

const agent = await builder
  .addUvicornApp('agent', './src/agent', 'app.main:app')
  .withUv()
  .publishAsDockerFile(async (container) => {
    await container
      .withDockerfile('.', { dockerfilePath: 'src/agent/Dockerfile' })
      .withEndpointCallback('http', async (endpoint) => {
        await endpoint.targetPort.set(8000);
      });
  })
  .withEnvironment('FOUNDRY_PROJECT_ENDPOINT', foundryProjectEndpoint)
  .withEnvironment('FOUNDRY_MODEL_DEPLOYMENT_NAME', foundryModelDeploymentName)
  .withEnvironment('MCP_URL', mcpEndpoint)
  .withReference(mcp)
  .waitFor(mcp)
  .withHttpHealthCheck({ path: '/health' });

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
  .withExternalHttpEndpoints();

await builder.build().run();
