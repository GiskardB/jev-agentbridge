// JEV-CPU-AgentBridge — OpenCode plugin.
//
// Provides a single callable tool:
//   jev_decide
// which calls POST /v1/decide on the JEV-CPU-AgentBridge service.
//
// OpenCode loads this as a server plugin. Add to your opencode.json:
//   { "plugin": ["./integrations/opencode/plugin/jev-cpu-agentbridge.mjs"] }

export default async ({ client } = {}) => {
  const log = (level, message) => {
    try {
      client && client.app && client.app.log({ body: { service: 'jev-cpu-agentbridge', level, message } });
    } catch (e) {}
  };

  let baseUrl = 'http://localhost:8000';

  return {
    config: async (config) => {
      config.skills = config.skills || {};
      config.skills.paths = config.skills.paths || [];
      // Allow users to configure the bridge URL via environment variable or config.
      if (process.env.JEV_CPU_AGENTBRIDGE_URL) {
        baseUrl = process.env.JEV_CPU_AGENTBRIDGE_URL;
        log('info', `JEV-CPU-AgentBridge URL: ${baseUrl}`);
      }
    },

    // Register the jev_decide tool.
    'tool.jev_decide': {
      description: 'Evaluate a discrete decision using the local JEV-CPU-AgentBridge.',
      // OpenCode tools accept a JSON input and return a JSON result.
      async call(input) {
        try {
          const response = await fetch(`${baseUrl}/v1/decide`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(input),
          });
          const body = await response.json();
          if (!response.ok) {
            return { error: body.error || { message: `Request failed: ${response.status}` } };
          }
          return body;
        } catch (err) {
          log('error', `jev_decide failed: ${err.message}`);
          return { error: { code: 'ENGINE_ERROR', message: err.message } };
        }
      },
    },
  };
};
