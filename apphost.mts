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

await builder
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

await builder
  .addViteApp('web', './src/web')
  .withEnvironment('API_URL', apiEndpoint)
  .withEnvironment('API_UPSTREAM', apiEndpoint)
  .withReference(api)
  .waitFor(api)
  .publishAsDockerFile(async (container) => {
    await container.withEndpointCallback('http', async (endpoint) => {
      await endpoint.targetPort.set(8080);
    });
  })
  .withExternalHttpEndpoints();

await builder.build().run();
