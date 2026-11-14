# What the backgrounds of the 35 reference thumbnails do (viewed one by one, 14 Nov 2026)

Measured over all 35 (docs/reference_analysis/taklipu_35_metrics.json): median brightness 0.41, median saturation 0.50,
sharpness is uniform across left/middle/right (no blurred sides): the whole frame is sharp, depth comes from lighting not blur.

## The key insight (outside the box)
The background is NEVER a generic "pretty plate". It is the LITERAL place where the story happens, and the person is INSIDE it:
- the person touches / holds / points at / sits in the topic object (envelope, passport, diamonds sack, gavel, ballot box, red button, quiz board)
- the object is big, in front of the body, partly overlapping the person (depth by overlap)
- background elements repeat the topic 3-5 times (Discord list with red X marks, airplane + Israeli flag on a video player, scales + law books)
- the generator renders person + scene as ONE image (lighting on the face comes from the scene). A cut-out on a plate cannot fully fake this.
=> best strategy: give the image tool the sharp AI portraits as references and ask for the WHOLE scene (portrait + environment + prop interaction).
   Our code then adds only the headline, QA, finishing. Compositing is the fallback.

## Background recipes by topic (observed)
| Topic | Environment (what is behind the face) | Prop interaction | Colour story |
|---|---|---|---|
| Lawsuit letter | dark-wood law office, books, scales, desk lamp | holds giant stamped envelope with wax seal toward camera | warm brown + red stamp |
| Heist / Rob Run | wrecked jewellery shop, broken glass, police lights outside | clutches a sack of cash / diamonds | red-blue police light split |
| Gold weapon | rainy alley at night, graffiti wall, police car | aims a gold rifle at camera | blue-red neon on wet street |
| Airport / leave everything | departures hall, flight board, check-in desk | holds passport + boarding pass, pilot uniform | cool daylight blue + warm sun |
| Birthday | party room, balloons, string lights, Discord logo | holds cake with number candles, party hats | purple + gold |
| Dating show / quiz | TV studio, neon hearts, LED set, ON AIR sign | heart card, giant guess-who board | purple, pink, gold |
| Trivia board | blue-purple arena | points at coloured quiz grid with money values | saturated rainbow on dark blue |
| Call / order drama | his gaming room (blurred) | phone at ear + big UI mock (order list, chat) | warm room, cyan UI |
| AI / tech | server room, robot arms | scientist coat + goggles, holds a tiny robot | cool blue + white |
| King / strategy game | throne-room feel, world-map screen | crown, sceptre, red velvet robe | gold + red |
| Court / ban | Discord member list full of red X, gavel | hits a gavel with sparks | red-orange fire on dark blue |
| Horror / lock the house | dark room, orange window light, shadow monster | peeks over shoulder | black + orange |
| Election / fraud | ballot box with Israeli emblem | guests stuffing papers | yellow burst + blue |
| Hand-on-head fail | blue/red split-light arena | both hands in hair, mouth open | RED on one side vs BLUE on the other |

## Lighting rules seen everywhere
1. SPLIT colour lighting: warm (red/orange/gold) on one side of the frame, cool (blue/cyan/purple) on the other; the face is lit from the cool side with a warm rim.
2. Dark vivid background, bright subject, strong contrast between face and background (face is the brightest, most saturated area).
3. Glow / sparks / light rays around the key prop (gavel sparks, red button glow, diamonds sparkle).
4. Large sharp props at the bottom edge of the frame bleeding out (chest, passport, cake) = a "foreground" layer in front of the body.
5. Text sits on the least busy region; busy backgrounds get a dark scrim only under the text.

## Face / pose rules
Eyes large and in the upper third; extreme expression; hands used (pointing, hands in hair, holding the prop) - hands are the second most important thing after the face.
Guests: same scene, smaller, own reaction, on the opposite side of the prop.

## What our code can and cannot do about it
- CAN: headline, split-colour background plates, rim light, prop drawn as vector UI (call, quiz, chat, order list), finishing grade, QA.
- CANNOT: photoreal environments with the person lit by them, hands touching props, costumes. -> needs the image tool (portraits as references).
