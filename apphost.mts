// Aspire TypeScript AppHost
// For more information, see: https://aspire.dev

import { createBuilder } from './.aspire/modules/aspire.mjs';

const builder = await createBuilder();

const api = await builder
  .addUvicornApp('api', './src/api', 'app.main:app')
  .withUv()
  .withHttpHealthCheck({ path: '/api/health' });

const apiEndpoint = api.getEndpoint('http');

await builder
  .addViteApp('web', './src/web')
  .withEnvironment('API_URL', apiEndpoint)
  .withReference(api)
  .waitFor(api)
  .withExternalHttpEndpoints();

await builder.build().run();