# Thumbnail brief (owner's required style)

The owner's reference style (Taklipu / ODED HIGHLIGHTS channel): ONE cohesive photorealistic AI scene that matches the video topic
(e.g. "first time in GTA 6" = GTA 6 cover vibe), built from real face reference frames, big expressive face, props matching the topic,
Hebrew headline of 2-3 words added on top (white + accent word, thick black stroke), never covering faces. No collages.
Composite-from-video-frames thumbnails were rejected by the owner ("not good at all").

## Workflow (no paid API available)
1. Claude writes the per-clip prompt below (scene, expression, props, free headline area) and picks 2-3 sharp face reference frames.
2. An image model that accepts reference faces generates the scene (Grok Bot GenerateImage, or Gemini/ChatGPT by hand).
3. `python3 scripts/thumb_maker.py --scene scene.png --head "..." --accent "..." --theme money --out thumb.jpg`
   adds the Hebrew headline in the free area, checks it does not cover faces (YuNet), size < 2 MB, and writes a 168x94 preview.

## Prompt template
> Photorealistic cinematic YouTube thumbnail, 16:9, ultra sharp, vivid saturated lighting. The streamer from the reference photos
> (keep his exact face, beard, dark hair and black headphones, no retouching, same identity) is the hero, large in frame, with an
> extreme expressive face: {EXPRESSION}. Scene and props that tell the story of the video: {SCENE_AND_PROPS}. {OTHER_PEOPLE}.
> Leave the top 28% of the image fairly clean and darker for a headline. No text, no logos, no watermarks, no extra fingers.

## Example: "Oded's first time entering GTA 6"
- EXPRESSION: jaw dropped, eyes wide, pure awe, one hand on his head
- SCENE_AND_PROPS: neon Vice City sunset behind him, pink and purple sky, palm trees, a glowing luxury sports car, a PS5 controller in his hand, game-cover composition
- OTHER_PEOPLE: none
- Headline: "ראשון" + accent "ב-GTA 6!" (theme money or party)
