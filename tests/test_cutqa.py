import os, subprocess, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import cutqa as Q, synth
class Boundaries(unittest.TestCase):
    segs = [{"start": 10.0, "end": 14.0, "text": "I went to the store."}, {"start": 14.5, "end": 18.0, "text": "And then it happened"}, {"start": 18.1, "end": 21.0, "text": "Everyone laughed!"}]
    def test_start_mid_segment(self): self.assertTrue(Q.seg_boundary(12.0, self.segs, "start")["mid"])
    def test_start_at_sentence(self):
        r = Q.seg_boundary(14.4, self.segs, "start"); self.assertFalse(r["mid"]); self.assertTrue(r["sentence_ok"])
    def test_start_after_unfinished_sentence(self):
        r = Q.seg_boundary(18.1, self.segs, "start"); self.assertFalse(r["mid"]); self.assertFalse(r["sentence_ok"])   # previous segment has no final punctuation and no pause
    def test_end_ok_and_mid(self):
        self.assertTrue(Q.seg_boundary(21.2, self.segs, "end")["sentence_ok"]); self.assertTrue(Q.seg_boundary(16.0, self.segs, "end")["mid"])
    def test_stretched_segment_ignored(self):
        self.assertFalse(Q.seg_boundary(100, [{"start": 0, "end": 248, "text": "x"}], "start")["mid"])
    def test_word_boundary(self):
        ws = [{"word": "hello", "start": 1.0, "end": 1.4}, {"word": "world", "start": 1.5, "end": 2.0}]
        self.assertTrue(Q.word_boundary(1.2, ws, "start")["inside_word"]); self.assertFalse(Q.word_boundary(1.45, ws, "start")["inside_word"]); self.assertAlmostEqual(Q.word_boundary(2.3, ws, "end")["gap"], 0.3, 2)
class Titles(unittest.TestCase):
    T = "so I played my song live at twitchcon and the whole crowd went crazy about Bam Margera and 40 skaters" 
    def test_supported(self): self.assertEqual(Q.title_truth("N3on played his song at TwitchCon", self.T, ["N3on"])["missing_names"], [])
    def test_invented_number_and_name(self):
        r = Q.title_truth("N3on Wins 500 Dollars From Drake", self.T, ["N3on"]); self.assertIn("Drake", r["missing_names"]); self.assertIn("500", r["missing_names"])
    def test_invented_quote(self): self.assertTrue(Q.title_truth('He says "I am quitting streaming forever" live', self.T)["bad_quotes"])
    def test_real_quote(self): self.assertFalse(Q.title_truth('He says "my song live" at the show', self.T)["bad_quotes"])
    def test_stem_support(self): self.assertEqual(Q.title_truth("The skating crowd", "skaters everywhere in the crowd " * 5)["missing_words"], [])
    def test_hebrew_transcript_skips_latin(self): self.assertEqual(Q.title_truth("עודד משחק Rob Run", "עודד משחק במשחק חדש " * 10)["missing_names"], [])
    def test_flags(self): self.assertTrue(Q.title_flags("This epic reveal will shock you")); self.assertFalse(Q.title_flags("N3on talks about his new song at TwitchCon"))
class Dups(unittest.TestCase):
    def test_overlap(self): self.assertAlmostEqual(Q.overlap(0, 10, 5, 20), 0.5)
    def test_dups(self):
        it = [{"id": "a", "vod": 1, "start": 100, "end": 130, "kind": "short"}, {"id": "b", "vod": 1, "start": 105, "end": 128, "kind": "short"}, {"id": "c", "vod": 2, "start": 100, "end": 130, "kind": "short"}]
        self.assertEqual([(a, b) for a, b, _ in Q.find_duplicates(it)], [("a", "b")])
class Audio(unittest.TestCase):
    def _clip(self, words, total, name):
        d = tempfile.mkdtemp(); w = os.path.join(d, name + ".wav"); synth.write_wav(w, synth.make_speech(words, total)); m = os.path.join(d, name + ".mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"color=c=gray:s=160x90:r=30:d={total}", "-i", w, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", m], check=True); return m
    def test_clean_cut_vs_dead_air_vs_abrupt(self):
        w, end = synth.sentence(0.3, 8)
        clean = Q.audio_report(self._clip(w, end + 0.35, "clean"))
        self.assertLess(clean["lead_silence_s"], 0.5); self.assertLess(clean["trail_silence_s"], 0.7); self.assertLess(clean["tail_rel_speech_db"], -15)
        dead = Q.audio_report(self._clip([(x + 2.5, y + 2.5) for x, y in w], end + 2.5 + 3.0, "dead")); self.assertGreater(dead["lead_silence_s"], 2.0); self.assertGreater(dead["trail_silence_s"], 2.5)
        abrupt = Q.audio_report(self._clip(w, end - 0.1, "abrupt")); self.assertGreater(abrupt["tail_rel_speech_db"], -9)   # cut while the last word is loud
    def test_grade_flags(self):
        w, end = synth.sentence(0.3, 8); m = self._clip(w, end - 0.1, "abrupt"); g = Q.grade(m, "short", title="N3on plays a song at the stage")
        self.assertTrue(any("abruptly" in x for x in g["warn"]))
        ws = [{"word": "w", "start": a, "end": b} for a, b in w]; g2 = Q.grade(m, "short", words=ws); self.assertTrue(any("ends inside the word" in x for x in g2["fail"]))
        g3 = Q.grade(self._clip([(x + 2.5, y + 2.5) for x, y in w], end + 5.5, "dead"), "short"); self.assertTrue(any("dead air" in x for x in g3["fail"] + g3["warn"]))
class Captions(unittest.TestCase):
    def test_overflow(self):
        ass = os.path.join(tempfile.mkdtemp(), "a.ass")
        open(ass, "w", encoding="utf-8").write("[Script Info]\nPlayResX: 1080\nPlayResY: 1920\n\n[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\nStyle: Cap,Heebo Black,104,&H0028E678,&H0028E678,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,9,3,2,60,60,610,1\n\n[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
            "Dialogue: 0,0:00:00.00,0:00:01.00,Cap,,0,0,0,,{\\fscx80}hello there\nDialogue: 0,0:00:01.00,0:00:02.00,Cap,,0,0,0,,Supercalifragilisticexpialidocious\n")
        r = Q.caption_report(ass, 2.0); self.assertEqual(len(r["overflow"]), 1); self.assertEqual(r["overflow"][0]["text"], "Supercalifragilisticexpialidocious")
if __name__ == "__main__": unittest.main()
