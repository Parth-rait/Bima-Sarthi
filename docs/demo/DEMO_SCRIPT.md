# Bima Sarthi: 3-minute demo script

What the video has to do in three minutes: show one claim going from a rejection letter to a cited answer and a plan, then say in plain words how it was built and why the answer can be trusted.

- Length: 3:00. About 430 spoken words at an easy pace (150 words a minute).
- Document: `docs/demo/sample-rejection-letter.pdf`. It is fictional on purpose (fictional insurer, person and policy, marked SAMPLE on the page). Do not record with a real letter: while the Baseten key is refused, reading goes to free-tier models whose inputs may be kept by the provider.
- The one statistic used is from `docs/ground-truth/GROUND_TRUTH.md` (CIO 2023-24: 31,490 health complaints, confirmed). Do not add others unless they are confirmed there.

---

## 1. Before you record (10 minutes)

1. **Servers.** Both must be running:
   ```
   cd "/Users/parthrait/Desktop/Bima Sarthi"
   curl -s http://localhost:8000/health        # backend: {"status":"ok"}
   curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5173/   # website: 200
   ```
   If the backend is down:
   ```
   nohup uv run --env-file .env uvicorn sarthi.app.main:app --host 127.0.0.1 --port 8000 >> /tmp/bima-backend.log 2>&1 &
   ```
   If the website is down: `cd frontend && npm run dev`
2. **Check the AI reader answers** (one line, about 1 second when healthy):
   ```
   uv run --env-file .env python -m sarthi.llm.client --role reader --ping
   ```
3. **Do one full practice run** with the sample letter (upload, confirm, run the check). You will see the exact screens below, and you will know how long reading takes today. Reading is the only slow part: a few seconds when the free model is healthy, up to a minute or two when it is not. You will cut that wait out afterwards (section 4), so do not rush it while recording.
4. **The screen.**
   - One Chrome window, only the Bima Sarthi tab open, zoom 100% (Cmd+0).
   - Hide the bookmarks bar (Cmd+Shift+B).
   - Turn on Do Not Disturb (Control Centre, Focus), so no notification appears in the video.
   - Close Slack, mail and anything that can pop up.
   - Start on http://localhost:5173/ scrolled to the top, in English.
5. **Sound.** A quiet room; earphones with a mic are clearer than the laptop mic. Do a 10-second test (section 3) and listen back.

---

## 2. The script

Each scene: what is on screen, what you do, what you say. The times are a guide; the words matter more.

### 0:00 to 0:20. The problem (Home page)

**Screen:** the home page, top. Do nothing for the first sentence, then move the pointer to the glowing "Check my claim" button.

**Say:**
> When an Indian health insurer rejects a claim, the letter usually gives one line of reason and no rule. In 2023-24 the Insurance Ombudsman received 31,490 health-insurance complaints. Most people never find out whether the rejection was even allowed. Bima Sarthi checks the decision against the IRDAI rules, and shows its working.

### 0:20 to 0:40. Upload

**Screen:** click "Check my claim". The upload card appears with its light running round the edge. Click "Choose files", pick `docs/demo/sample-rejection-letter.pdf`, then press "Read my documents".

**Say:**
> You upload the rejection letter, as a PDF or a phone photo. Here is a sample letter: the insurer refused a heart-disease claim, saying the pre-existing-disease waiting period is 48 months and not over.

(The reading wait is cut here in editing. Keep talking only once the Confirm screen is up.)

### 0:40 to 1:10. Confirm, and going back

**Screen:** the Confirm screen. Scroll slowly through the facts. Point at one fact's quote from the letter. Answer the one or two questions marked to confirm. Then click "1. Upload" in the step bar at the top, show the upload sheet for a second, click "2. Confirm" to come back, and press "Run the check".

**Say:**
> A vision model reads the letter, but it does not decide anything. Every fact it pulls out comes with the exact words from the letter, and anything it is unsure of, you confirm. You can step back to any stage at any time. Your answers are kept.

### 1:10 to 1:55. The result

**Screen:** the Result. Stay on the verdict card first; point at the quoted rule and its page. Scroll to "Your result in one picture" and point at the two bars. Scroll to the deadline chart, then to the plan's route map and click one stop (the page scrolls to that step).

**Say:**
> The answer: challengeable. The rule is quoted word for word from the IRDAI Products Regulations, with its page: the waiting period for a disclosed pre-existing disease can be at most 36 months, and this policy has been continuous since 2019.
> This picture is counts, not a guess at your chances: which rules were checked and what each said, and real court cases with the same stated reason and who won them.
> Then the deadlines, by date, and a step-by-step plan: what to ask the insurer for, the grievance letter, and when you can go to the Ombudsman.

### 1:55 to 2:10. Letter and schemes

**Screen:** at the end of the result, click "Download grievance letter (PDF)" (show the file appearing, do not open it). Then open "Find schemes" in the top menu and show the four questions.

**Say:**
> It writes the grievance letter for you, with the rule and the deadline in it. And for farm workers in Maharashtra, four questions show which government schemes fit and how a claim on them can fail.

### 2:10 to 2:50. How it was built

**Screen:** open http://localhost:5173/evidence (the evaluation page). If you prefer, show the architecture diagram in the README on GitHub instead.

**Say:**
> How it works: models read, code decides. A vision model, Spark Open with free fallbacks, turns the letter into facts with their quotes. Then a deterministic rule engine applies rule cards, each quoting the regulation verbatim with its page. A card only goes live after a person approves it; nine are live today. The rules come from Airflow pipelines that fetch the IRDAI documents, and the same pipelines run the evaluation against real court judgments. The backend is FastAPI with DuckDB; the website is React. There are over 1,700 automated tests. And this page shows the evaluation honestly: on every reviewed court case so far, when a needed fact was missing, the engine asked instead of guessing, so it never gave false hope.

### 2:50 to 3:00. Close

**Screen:** back to the home page.

**Say:**
> Your documents are deleted after the result, or after one hour. It is a rules check, not legal advice. Bima Sarthi: know whether your rejection was allowed, and what to do next.

---

## 3. Recording the screen

### Easiest: the built-in recorder (no Terminal)

1. Press **Cmd+Shift+5**.
2. Choose **Record Selected Portion** (draw a box round the Chrome window) or **Record Entire Screen**.
3. Click **Options**: Microphone: your mic. Save to: Desktop. Turn on **Show Mouse Clicks**.
4. Click **Record**. Wait two seconds, then start talking.
5. To stop: click the stop button in the menu bar, or press **Cmd+Ctrl+Esc**. The video is saved on the Desktop.

The first time, macOS asks for Screen Recording permission (System Settings, Privacy & Security, Screen & System Audio Recording).

### From Terminal

10-second test first (records the main screen with your mic and shows clicks, then opens the result):
```
screencapture -v -g -k -V 10 ~/Desktop/test.mov && open ~/Desktop/test.mov
```
The real recording. It stops by itself after 210 seconds (3:30, leaving room for the reading wait you will cut):
```
screencapture -v -g -k -V 210 ~/Desktop/bima-demo.mov
```
- `-v` record video, `-g` record the default microphone, `-k` show clicks, `-V 210` stop after 210 seconds.
- Second display: add `-D 2`. A fixed area: add `-R x,y,width,height`.
- The first run asks Terminal for Screen Recording and Microphone permission; allow both, then run it again.

---

## 4. After recording: cut the wait and make it small

`ffmpeg` is installed (`/opt/homebrew/bin/ffmpeg`).

**Easiest trim:** open the file in QuickTime Player, press **Cmd+T**, drag the yellow handles to cut the start and end, then **File, Save**.

**Cut the reading wait out of the middle.** Note the second where you pressed "Read my documents" (say 38) and the second where Confirm appeared (say 95); this keeps 0 to 38 and 95 to the end:
```
cd ~/Desktop
ffmpeg -i bima-demo.mov -filter_complex "[0:v]trim=0:38,setpts=PTS-STARTPTS[v0];[0:a]atrim=0:38,asetpts=PTS-STARTPTS[a0];[0:v]trim=start=95,setpts=PTS-STARTPTS[v1];[0:a]atrim=start=95,asetpts=PTS-STARTPTS[a1];[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]" -map "[v]" -map "[a]" -c:v libx264 -crf 23 -preset medium -c:a aac -b:a 128k -movflags +faststart bima-demo-cut.mp4
```
**Make an upload-friendly MP4, capped at 3:00:**
```
ffmpeg -i bima-demo-cut.mp4 -t 180 -vf "scale=1920:-2" -c:v libx264 -crf 23 -preset medium -c:a aac -b:a 128k -movflags +faststart bima-demo-final.mp4
```
Check the length:
```
ffprobe -v error -show_entries format=duration -of csv=p=0 bima-demo-final.mp4
```

---

## 5. If something goes wrong while recording

- **Reading takes minutes, or ends with an error.** The free models are struggling. Wait a minute and press Read again; or fix the Baseten key (the paid reader) before recording.
- **The result says "Need info" instead of "Challengeable".** On Confirm, check that the policy renewal date (01/04/2025) and the disclosed condition (coronary artery disease) are there and confirmed. Without the renewal date the rule's start date cannot be checked, and the engine correctly refuses to guess.
- **Find schemes says the questions could not load.** The website must be the dev server on 5173 (it forwards `/api` to the backend), and the backend must be up.
