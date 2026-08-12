// pm2 config for the production frontend. On the server:
//   cd frontend && pnpm install && pnpm build
//   pm2 start ecosystem.config.js && pm2 save
// After deploying a new build: pm2 restart shevaani-frontend
//
// The port lives here (not in package.json) so each product on the server
// claims its own without touching the repo's scripts.
module.exports = {
  apps: [
    {
      name: "shevaani-frontend",
      script: "pnpm",
      args: "start",
      env: {
        NODE_ENV: "production",
        PORT: "3001",
      },
    },
  ],
};
