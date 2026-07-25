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
  .withEnvironment('NEIS_API_KEY', neisApiKey)
  .withHttpHealthCheck({ path: '/api/health' });

const apiEndpoint = api.getEndpoint('http');

await builder
  .addViteApp('web', './src/web')
  .withEnvironment('API_URL', apiEndpoint)
  .withReference(api)
  .waitFor(api)
  .publishAsStaticWebsite({ apiPath: '/api', apiTarget: api })
  .withExternalHttpEndpoints();

await builder.build().run();
