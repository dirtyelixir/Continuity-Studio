You are taking full ownership of a new project from zero.

I have intentionally not designed the product, UI, architecture, data model, workflow, provider system, skill system, or implementation for you.

You are responsible for deciding what the product should become and building a genuinely usable MVP.

# OBJECTIVE

Build an AI-assisted narrative production application that can take me from a simple idea to production-ready visual planning, generated visual assets, and MiniMax H3-ready prompts.

The target workflow is approximately:

IDEA
→ STORY
→ SCRIPT / DIALOGUE
→ SCENES
→ SHOTS
→ STORYBOARD / KEYFRAMES
→ CHARACTER ASSETS
→ LOCATION ASSETS
→ IMAGE PROMPTS
→ IMAGE GENERATION
→ MINIMAX H3 PROMPTS

The final MiniMax H3 video generation itself does not need to be part of the first MVP unless you independently determine that including it provides clear value without unnecessarily expanding the scope.

The core problem to solve is:

turning a story into coherent, reusable, production-ready shots, references, images and H3 prompts without requiring me to manually coordinate every prompt, reference image, file, asset, continuity decision and generation step.

# PRIMARY SUCCESS CRITERION

I should be able to give the system a creative objective or story idea and operate mainly at the level of:

* reviewing important creative decisions
* approving or rejecting results
* selecting alternatives
* changing creative direction when necessary

I should NOT need to manually manage:

* hundreds of prompts
* reference-image paths
* repeated character descriptions
* repeated location descriptions
* continuity notes
* asset reuse
* shot metadata
* prompt relationships
* generation state
* project-state recovery

The product should manage those relationships itself.

# ASTRA IS THE DEFAULT INTELLIGENCE

By default, every task that can reasonably be performed by Astra should be performed by Astra.

Astra should be the default creative and reasoning authority for areas such as:

* story generation
* story development
* screenplay
* dialogue
* scene breakdown
* shot design
* directing
* cinematography decisions
* storyboard planning
* character design decisions
* location design decisions
* asset planning
* reference selection
* image prompt generation
* image-generation planning
* generated-image review
* regeneration decisions
* continuity reasoning
* MiniMax H3 prompt generation
* quality review
* project-level creative decisions

Do not unnecessarily push these responsibilities to weaker local models merely to save tokens.

The default product experience should be Astra-driven.

# ASTRA-DEFAULT, BUT PROVIDER-SWITCHABLE

Although Astra is the default provider, the product architecture must NOT depend on Astra being permanently responsible for every replaceable capability.

Any capability that can sensibly be abstracted should be designed so that it can later be executed by:

* Astra — DEFAULT
* an external API
* another cloud model
* a local model
* a Codex Skill or compatible skill extension
* another deterministic service
* a human/manual workflow

without redesigning the entire application.

Think in terms of capabilities and providers rather than hard-coded model-specific workflows.

Where appropriate, capabilities such as:

* story generation
* screenplay/dialogue
* scene breakdown
* shot planning
* storyboard planning
* character design
* location design
* prompt generation
* image generation
* image review
* continuity review
* MiniMax H3 prompt generation
* QC

should be able to expose alternative providers while defaulting to Astra.

However:

Do NOT blindly build a provider abstraction for every tiny operation.

Use engineering judgment.

The architecture should remain understandable, maintainable and appropriately simple.

# IMAGE GENERATION

Image generation is part of the MVP.

The system must generate actual visual assets rather than merely writing prompts.

By default, Astra should own the creative image-generation workflow.

This includes:

* identifying which visual assets are required
* checking which approved assets already exist
* deciding whether an existing asset should be reused
* deciding whether a new asset is genuinely required
* deciding which reference images are relevant
* constructing the image-generation instruction
* choosing the appropriate generation capability/provider
* initiating image generation
* inspecting generated results where technically possible
* evaluating whether the image satisfies the intended shot or asset requirement
* evaluating character/location continuity
* deciding whether regeneration or revision is required
* preserving approved assets for later reuse

Actual image rendering may be performed through:

* an Astra-accessible image-generation capability
* an external image-generation API
* a Skill
* another cloud provider
* a local generation backend
* another appropriate future provider

The system should not assume one permanent image-generation backend.

Do not make local generation the default merely because local models are present.

The default creative authority remains Astra.

# CONTINUITY IS A FIRST-CLASS SYSTEM

Continuity is one of the highest-priority requirements of the product.

Do not treat continuity as simply repeating long character descriptions inside prompts.

Design a persistent canonical system for established facts and approved visual identity.

The system should be capable of maintaining, where relevant:

* character identity
* facial appearance
* body proportions
* hairstyle
* clothing
* accessories
* personality
* relationships
* recurring props
* location identity
* spatial characteristics
* established visual references
* approved reference images
* story canon
* scene state
* previous-shot state
* scene-to-scene continuity
* shot-to-shot continuity

When creating a new:

* shot
* storyboard
* image prompt
* visual asset
* H3 prompt

the application should automatically retrieve and apply the relevant established information.

Do not rely on conversation history as the primary source of truth.

# STORY / SCENE / SHOT PRODUCTION MODEL

The system should reason in production units rather than treating the complete story as one giant prompt.

Determine the most appropriate hierarchy yourself.

Production units should preserve explicit relationships between relevant elements such as:

* story
* scenes
* shots
* dialogue
* characters
* locations
* props
* actions
* storyboard frames
* reference assets
* generated assets
* image prompts
* H3 prompts
* production status

Do not force the user to manually maintain those relationships.

# STORYBOARD DESIGN

Storyboard generation must be shot-oriented.

A storyboard frame should normally represent one precise visual moment.

Avoid describing several sequential actions inside one frame when multiple keyframes would communicate the intended action more reliably.

For example:

Bad storyboard frame:

"Chloe walks toward the sofa, sits down, picks up Milo and Milo jumps away."

Better production breakdown:

Frame A:
Chloe is approaching the sofa.

Frame B:
Chloe is seated beside Milo.

Frame C:
Chloe has lifted Milo.

Frame D:
Milo has just jumped away.

Determine when multiple keyframes are genuinely useful rather than mechanically creating unnecessary frames.

# CINEMATOGRAPHY

Shot direction should be specific enough to produce actionable visual and MiniMax H3 prompts.

Avoid vague descriptions such as:

"cinematic camera movement"

when clearer instructions can be given.

Prefer instructions such as:

"slow dolly from medium-wide to medium close-up"

or:

"at approximately 4 seconds, rapid push-in toward the character's face for comedic emphasis."

The system should reason about, where appropriate:

* framing
* shot size
* camera angle
* camera movement
* blocking
* screen direction
* facial expression
* body action
* important timing beats
* start composition
* end composition

# MINIMAX H3

One of the final outputs for each relevant shot should be a production-ready MiniMax H3 prompt.

Design the system so that H3 prompts are generated from structured production information rather than generic prose generated from scratch.

Where appropriate, H3 prompt generation should understand:

* shot duration
* starting visual state
* ending visual state
* character action
* facial expression
* body movement
* dialogue
* dialogue timing
* camera framing
* camera angle
* camera movement
* important timed beats
* reference images
* character continuity
* location continuity
* adjacent-shot continuity

Research current MiniMax H3 prompting practices and requirements where necessary rather than relying on outdated assumptions.

The system should make it possible to improve or replace the H3 prompt-generation capability later through another provider, API or Skill.

# EXTENSIBILITY AND SKILLS

The product must be designed as an extensible system.

Skills should be treated as a first-class extension mechanism rather than an afterthought.

Astra remains the default intelligence and creative authority.

Installing a Skill must not silently replace Astra as the default provider unless the user explicitly changes that preference.

The system should be capable of incorporating specialized Skills for areas such as, where useful:

* story development
* screenplay/dialogue
* shot design
* storyboard generation
* cinematography
* character consistency
* location consistency
* asset creation
* image generation
* image editing
* prompt generation
* MiniMax H3 prompting
* quality control
* provider integrations

These examples are NOT a prescribed Skill architecture.

You should independently determine:

* what a Skill should represent in this product
* how Skills are discovered
* how Skills are installed or registered
* how Skills expose capabilities
* how Astra selects or invokes Skills
* how users enable or disable Skills
* how Skills are configured
* how Skills interact with APIs/providers
* how failures are handled
* how permissions are handled
* whether Skills should be composable
* how Skill versions are managed
* how compatibility is managed
* what UI should exist for Skills
* how Skill-provided capabilities appear in the application

Do not build the core product around a fixed list of built-in workflows.

A future Skill should be able to add a meaningful new production capability without requiring the core application to be substantially redesigned.

Research the current Codex Skills system and other relevant extension mechanisms before deciding how to implement this.

# PRODUCT DESIGN AUTONOMY

You decide:

* what the product actually is
* project organization
* UX
* UI
* navigation
* data model
* persistence architecture
* database/storage approach
* asset representation
* reference representation
* revision history
* production workflow
* production states
* provider interfaces
* Skill architecture
* agent architecture
* technology stack
* frontend/backend architecture
* local/cloud boundaries
* automation level
* human approval points
* failure/retry behavior
* MVP scope
* which features should be postponed

I am deliberately NOT prescribing:

* React
* Vue
* FastAPI
* SQLite
* PostgreSQL
* cards
* timelines
* canvases
* node graphs
* folders
* databases
* queues
* specific agents
* specific UI layouts

Do not inherit these choices merely because they are common.

Research first and choose deliberately.

# PRIOR ART

Research ToonFlow as relevant prior art.

Study the problem it attempts to solve rather than simply copying its visual design.

Where accessible, evaluate:

* product philosophy
* workflow
* project model
* story-to-shot process
* character handling
* location handling
* asset handling
* storyboard experience
* generation workflow
* provider architecture
* persistence
* extension model
* UX strengths
* UX weaknesses
* architectural strengths
* architectural weaknesses

Also research other relevant:

* storytelling tools
* storyboard tools
* filmmaking tools
* previsualization tools
* AI video-production systems
* AI image-production systems

if they materially improve the product design.

Do NOT clone ToonFlow by default.

Do NOT reject ToonFlow merely to be different.

Use useful ideas when justified and design the product around my actual objective.

# LOCAL ENVIRONMENT

Inspect the actual environment where useful.

Existing resources may include:

* ComfyUI
* local Qwen models
* image-generation models
* image-editing models
* MiniMax H3 workflows
* APIs
* other local or cloud generation services

Do not assume exactly how these systems are configured.

Inspect before integrating.

Do not redesign the entire product around an existing local tool merely because it is installed.

Existing infrastructure is a resource, not a mandatory architecture.

# DELEGATION

Astra remains the owner of:

* product decisions
* architecture
* UX
* creative direction
* continuity strategy
* provider strategy
* Skill strategy
* major implementation decisions
* final acceptance

Delegation is allowed only where it genuinely reduces total effort.

Do not create a workflow where Astra becomes a babysitter for weaker workers.

Delegate bounded work when:

* the task is clearly specified
* the expected result is well-defined
* the result is inexpensive to verify
* failure is inexpensive to recover from
* delegation is genuinely more efficient

Do not delegate important product or creative decisions merely to save quota.

# AUTONOMY

Do not repeatedly ask me to choose between technical approaches that you are capable of evaluating yourself.

If a decision is:

* technical
* reversible
* researchable
* reasonably inferable from the objective

then make the decision yourself.

Document significant assumptions and major architectural decisions.

Escalate to me only when a decision is genuinely subjective, materially changes the product I will receive, and cannot reasonably be inferred from the objective.

When information is missing but a sensible reversible assumption can be made, make the assumption and proceed.

# PERSISTENT PROJECT STATE

This project must not depend on one long chat thread.

Create whatever durable project documentation, canonical state, registries, database structures or machine-readable persistence you determine are appropriate.

Future Astra sessions should be able to inspect the project and understand:

* what the product is
* how it works
* why major decisions were made
* what has been implemented
* current implementation state
* current production state
* known limitations
* unresolved issues
* how to continue safely

Do not use chat memory as the database.

# DO NOT FAKE COMPLETION

Do not stop after producing:

* research notes
* a product specification
* architecture documents
* wireframes
* mockups
* screenshots
* static HTML
* fake buttons
* placeholder generation
* disconnected frontend screens
* non-functional integrations

The target is a usable MVP.

Important workflows must actually work.

Where real integrations are available, use them.

Do not mark a feature complete merely because code exists.

Run it.

Exercise it.

Verify its outputs.

Fix failures that prevent normal use.

# MVP ACCEPTANCE TARGET

A successful MVP should allow a real small narrative project to be taken through a meaningful end-to-end workflow inside the application.

At minimum, I should be able to:

1. create or enter a story idea

2. develop it into usable narrative content

3. create dialogue where relevant

4. break the narrative into appropriate production units

5. obtain coherent shot planning

6. obtain storyboard/keyframe planning

7. establish reusable character identities

8. establish reusable location identities

9. create and manage visual reference assets

10. generate actual character/location/storyboard-related images through an available image-generation provider

11. preserve character identity across relevant generated images

12. preserve location continuity across relevant generated images

13. understand which assets/references belong to which shots

14. automatically reuse approved assets when appropriate

15. generate usable image-generation prompts

16. generate production-ready MiniMax H3 prompts

17. switch appropriate capabilities away from Astra to another API/provider/Skill when configured

18. return to the same project later without losing established canon, continuity or asset relationships

The exact UI and workflow for accomplishing this are your responsibility.

# REPRESENTATIVE ACCEPTANCE TEST

Do not validate the MVP only with isolated unit features.

Use the finished application to create at least one representative small narrative project containing:

* more than one character or meaningful reusable visual identity where appropriate
* at least one established location
* multiple scenes or shots
* reusable reference assets
* storyboard/keyframe planning
* actual image generation
* continuity across multiple outputs
* image prompts
* MiniMax H3 prompts

Use the product as a real user would.

Identify friction, missing state, broken relationships and continuity failures.

Fix important problems before considering the MVP accepted.

# EXECUTION STRATEGY

Do not immediately begin coding the first architecture that comes to mind.

Start by understanding the actual problem.

Research enough to avoid obvious product and architectural mistakes.

Inspect the existing environment where useful.

Then:

1. define the product hypothesis
2. define the MVP boundary
3. decide the UX/workflow
4. decide the architecture
5. establish persistent project state
6. implement the MVP
7. run the application
8. exercise the real workflow
9. generate real outputs
10. evaluate the result as a user
11. fix important product, continuity, integration and usability failures
12. verify the MVP against the acceptance target

Preserve working checkpoints.

Do not repeatedly rewrite the entire product without evidence that a rewrite is necessary.

# COST / QUOTA AWARENESS

Be conscious that Astra reasoning and tool usage have cost.

Spend high-value reasoning on decisions where intelligence materially matters.

Avoid:

* repeatedly rereading huge context unnecessarily
* regenerating information already persisted
* unnecessary architectural rewrites
* repetitive research
* redundant tool calls
* excessive weak-worker delegation followed by expensive repair
* using high-value reasoning for mechanical work when a reliable cheaper method exists

However:

Do not reduce product quality merely to save quota.

Astra remains the default creative and reasoning authority.

Efficiency should come from good architecture, persistent state and appropriate delegation rather than from weakening the product.

# OWNERSHIP

You are acting as:

* product owner
* UX designer
* software architect
* technical lead
* AI workflow architect
* narrative-production workflow designer
* continuity-system designer
* Skill/platform designer
* implementation owner
* acceptance authority

Take ownership accordingly.

Do not wait for me to design the application for you.

# FIRST INSTRUCTION

Begin now.

First investigate:

* the problem space
* relevant prior art
* ToonFlow
* relevant current Skills mechanisms
* the actual local environment where useful
* viable image-generation options
* MiniMax H3 requirements where relevant

Then independently decide what product should be built.

Establish durable project state so future work does not depend on chat memory.

Proceed into implementation.

Continue toward a genuinely usable MVP.

Verify the core workflow with a representative real project.

Do not stop at planning.

Do not ask me to design the system for you.

Own the project from product definition through usable MVP and acceptance.
