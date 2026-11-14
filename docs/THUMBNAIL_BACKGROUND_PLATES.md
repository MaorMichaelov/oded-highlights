# Background plates (scene backgrounds WITHOUT people) - ask the image tool for these

Why: the reference thumbnails always have a LITERAL scene behind the face that tells the video's topic (jewellery store, law office, airport, casino...).
Plates are easy for an image model (no identity problem). We composite the sharp AI portrait, the story prop and the headline on top.

Base prompt (fill {SCENE}):
> Photorealistic cinematic background plate for a YouTube thumbnail, 16:9, ultra sharp, {SCENE}. Strong saturated colour story, dramatic lighting with
> a soft glow, shallow depth of field. The LEFT 45% of the frame is calm and slightly darker (empty space for a person), details concentrated on the right.
> NO people, NO text, NO logos, NO watermarks.

SCENE list (one plate per topic):
1. phone call / drama: dark neon city street at night, glowing smartphone light reflections on wet asphalt, orange and teal lights
2. game heist (Rob Run): inside a luxury jewellery store at night, glass cabinets with diamonds, blue police lights flashing through the window
3. money / merch / shopping: gold and green luxury vault, stacks of cash, golden rays
4. casino / gambling-style talk (no real gambling): casino floor with neon signs, red and gold, roulette table blurred in the background
5. courtroom / lawsuit letter: dark wood law office with books and scales of justice, warm lamp light
6. airport / leaving: bright airport terminal departures hall, large windows, warm sunset light
7. birthday / surprise: party room with balloons, confetti, string lights, purple and gold
8. TV studio / show / dating-show reaction: glossy talk-show studio, purple and pink neon, heart-shaped lights
9. quiz / trivia: game-show stage with colourful lit board and spotlights, blue and purple
10. gaming setup / streamer room: dark gaming room with RGB lights, monitors glow, purple-blue
11. game launch / GTA-style: neon sunset skyline of a tropical city, pink and purple sky, palm trees, cars
12. fight / drama / rage: stormy red and orange sky over a city, sparks and smoke
13. travel / trip gone wrong: hotel street at night with neon palm signs, purple lights, rain
14. food / shawarma: warm street food stall at night, grill smoke, orange lights
15. AI / tech: futuristic server room with blue light beams, holographic glow
16. sports / challenge: stadium floodlights, dramatic gold light, running track

Usage after the plates exist:
  python3 scripts/thumb_call.py --face oded_ai_faces/smirk.jpg --bg plate_phone.jpg --head "מתקשר" --accent "לעמית שיבר!" --out thumb.jpg
