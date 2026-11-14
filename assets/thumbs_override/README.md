# thumbs_override
Drop Grok Bot (or any hand-made) thumbnails here, named `<clip_id>_c.jpg` (first, uploaded with the video) and `<clip_id>_d.jpg` (second, for YouTube Test & compare).
If `<clip_id>_c.jpg` exists the pipeline uses it instead of the auto-generated thumbnail. 1280x720 JPG, under 2 MB.
How: GitHub web -> this folder -> Add file -> Upload files (no PC tools needed), or `git push` from Grok Bot if it has GitHub access.
Each clip's `state/clips/<id>/grok_request.md` holds a ready-to-paste Grok brief (topic, scene, headline).
