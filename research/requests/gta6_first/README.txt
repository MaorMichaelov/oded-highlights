REQUEST PACK: gta6_first
Topic: Oded enters GTA 6 for the first time
1. In Grok Bot call GenerateImage with: aspect_ratio "16:9", reference_image_paths = 2-3 faces from thumb_assets/faces/oded (best match for tag "awe": see index.json),
   description = the text of prompt.txt.  Ask for 2 variants (C and D) with different composition.
2. Save the images and send them back (or drop them in the repo folder research/requests/gta6_first/).
3. Headline to add: line 1 "הפעם הראשונה"  line 2 "ב-GTA 6!"  -> python3 scripts/thumb_maker.py --scene IMG --head "הפעם הראשונה" --accent "ב-GTA 6!" --ribbon --out thumb_c.jpg
