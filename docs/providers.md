# Provider connections and current account limitations

Checked against official/provider-maintainer documentation on 2026-10-05.
Connection availability can change; check your installed major version and
the authentication methods actually offered by `/connect`.

## OpenCode owns authentication

Use `/connect` followed by `/models` in OpenCode. The Python core contains no
LLM client, OAuth implementation or OpenRouter dependency. Provider/model
selection is inherited unless you add an override in OpenCode configuration.

OpenCode V1 and V2 use different config names. The project selector manages
only the project's profile and does not configure or verify your account.

- [V1 providers](https://opencode.ai/docs/providers/)
- [V2 providers](https://opencode.ai/v2/docs/providers)
- [V1 config](https://opencode.ai/docs/config/)
- [V2 config](https://opencode.ai/v2/docs/config)

## ChatGPT

The V1 OpenCode provider guide documents OpenAI > ChatGPT Plus/Pro authentication
through `/connect`. Choose a model actually available in your account. This is
not a promise that every ChatGPT model, endpoint or unlimited quota is exposed.
For V2, follow the methods offered by its current OpenAI integration rather than
assuming a V1 connection command stores credentials identically.

## Claude

The current OpenCode V1 provider page includes conflicting historical wording
about a Claude Pro/Max option, followed by a notice that subscription plugins are
no longer bundled as of 1.3.0 and that Anthropic prohibits their use. This project
therefore documents the Anthropic API connection instead of promising Claude
consumer subscription reuse. It does not install subscription-auth bypass plugins.

## Gemini

Google's official deprecation page states that consumer Gemini Code Assist and
Gemini CLI Login with Google access ended on June 18, 2026, including Google AI
Pro/Ultra tiers. Standard/Enterprise organization subscriptions are a separate
case. The maintained opencode-gemini-auth repository repeats the limitation.

- [Google consumer access deprecation](https://developers.google.com/gemini-code-assist/docs/deprecations/code-assist-individuals)
- [Gemini OAuth plugin maintainer](https://github.com/jenslys/opencode-gemini-auth)

Use a supported Gemini API-key or Vertex AI connection for this workflow. An
existing Gemini chat subscription should not be presented as equivalent to API
credits. No community authentication plugin is enabled automatically. If you
choose an external integration, check its current account eligibility and provider
documentation before adding it to your version's plugin configuration.

## Other providers and model overrides

Use any provider supported by your OpenCode version, including local ones.
Select models interactively; no model ID is hard-coded in this project. For per-stage
overrides, edit the command frontmatter model field or define extra agents using
your version's schema. Keep actual model/provider details in draft provenance when
available; never infer them from the skill name.

