"""Generate the Pixii Pulse submission-video guide as a styled PDF.

Run once with: python generate_video_guide.py
Output: VIDEO_GUIDE.pdf in the project root.
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT_PATH = Path(__file__).resolve().parent / "VIDEO_GUIDE.pdf"

# ---------------------------------------------------------------- styles ----
PRIMARY = colors.HexColor("#6D28D9")     # purple
INK = colors.HexColor("#0F172A")
INK_SOFT = colors.HexColor("#475569")
ACCENT = colors.HexColor("#EC4899")
PALE = colors.HexColor("#F5F3FF")
RULE = colors.HexColor("#E2E8F0")
ROW_ALT = colors.HexColor("#FAFAF9")

base = getSampleStyleSheet()


def style(name, **kwargs) -> ParagraphStyle:
    return ParagraphStyle(name, parent=base["BodyText"], **kwargs)


title_style = style(
    "Title",
    fontName="Helvetica-Bold",
    fontSize=28,
    leading=32,
    textColor=PRIMARY,
    alignment=TA_LEFT,
    spaceAfter=6,
)
subtitle_style = style(
    "Subtitle",
    fontName="Helvetica",
    fontSize=14,
    leading=18,
    textColor=INK_SOFT,
    alignment=TA_LEFT,
    spaceAfter=20,
)
h1_style = style(
    "H1",
    fontName="Helvetica-Bold",
    fontSize=18,
    leading=22,
    textColor=PRIMARY,
    spaceBefore=18,
    spaceAfter=10,
)
h2_style = style(
    "H2",
    fontName="Helvetica-Bold",
    fontSize=13,
    leading=17,
    textColor=INK,
    spaceBefore=14,
    spaceAfter=6,
)
body = style(
    "Body",
    fontName="Helvetica",
    fontSize=10.5,
    leading=15,
    textColor=INK,
    spaceAfter=8,
)
body_soft = style(
    "BodySoft",
    fontName="Helvetica",
    fontSize=10,
    leading=14,
    textColor=INK_SOFT,
    spaceAfter=6,
)
quote_style = style(
    "Quote",
    fontName="Helvetica-Oblique",
    fontSize=11,
    leading=15,
    textColor=PRIMARY,
    leftIndent=14,
    rightIndent=10,
    spaceBefore=8,
    spaceAfter=8,
    borderColor=PRIMARY,
    borderPadding=8,
    borderWidth=0,
    backColor=PALE,
)
script_style = style(
    "Script",
    fontName="Helvetica",
    fontSize=10.5,
    leading=15,
    textColor=INK,
    leftIndent=18,
    rightIndent=12,
    spaceAfter=10,
    borderColor=PRIMARY,
    borderPadding=10,
    borderWidth=0,
    backColor=colors.HexColor("#FFFBEB"),
)
checklist_style = style(
    "Checklist",
    fontName="Helvetica",
    fontSize=10.5,
    leading=16,
    textColor=INK,
    leftIndent=10,
    spaceAfter=2,
)
footer_style = style(
    "Footer",
    fontName="Helvetica",
    fontSize=8,
    leading=10,
    textColor=INK_SOFT,
    alignment=TA_CENTER,
)


# ---------------------------------------------------------------- helpers ----
def hr() -> HRFlowable:
    return HRFlowable(width="100%", thickness=0.6, color=RULE, spaceBefore=8, spaceAfter=8)


def make_table(data, col_widths, header=True, alt_rows=True):
    t = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)
    cmds = [
        ("FONT", (0, 0), (-1, -1), "Helvetica", 9.5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, RULE),
    ]
    if header:
        cmds += [
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9.5),
            ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("LINEBELOW", (0, 0), (-1, 0), 0, colors.white),
        ]
    if alt_rows:
        for i in range(1 if header else 0, len(data)):
            if i % 2 == 0:
                cmds.append(("BACKGROUND", (0, i), (-1, i), ROW_ALT))
    t.setStyle(TableStyle(cmds))
    return t


def page_decoration(canv, doc):
    canv.saveState()
    # Thin top line in primary color
    canv.setStrokeColor(PRIMARY)
    canv.setLineWidth(2.5)
    canv.line(0.6 * inch, LETTER[1] - 0.45 * inch, LETTER[0] - 0.6 * inch, LETTER[1] - 0.45 * inch)
    # Footer
    canv.setFont("Helvetica", 8)
    canv.setFillColor(INK_SOFT)
    canv.drawString(0.6 * inch, 0.4 * inch, "Pixii Pulse — Submission Video Guide")
    canv.drawRightString(
        LETTER[0] - 0.6 * inch,
        0.4 * inch,
        f"Page {canv.getPageNumber()}",
    )
    canv.restoreState()


# ---------------------------------------------------------------- content ----
def build_story():
    s = []

    # ---- TITLE PAGE ----
    s.append(Paragraph("PIXII PULSE", title_style))
    s.append(Paragraph("Submission Video Guide", subtitle_style))
    s.append(hr())
    s.append(
        Paragraph(
            "<b>3 minutes. One take. The most important video you will record this month.</b>",
            body,
        )
    )
    s.append(
        Paragraph(
            "This guide covers everything: the structure, the verbatim script, what to show on screen at each "
            "second, what to wear, what to avoid, and the small touches that separate you from the next candidate. "
            "Read it once. Practise three times. Record on the fourth.",
            body,
        )
    )

    # ---- SECTION 1 ----
    s.append(Paragraph("1. Why this video is your only shot", h1_style))
    s.append(
        Paragraph(
            "Pixii is reviewing dozens of submissions. Reviewers spend roughly three minutes deciding yes or no. "
            "Your code is opened only if your video hooks them. That makes this short clip about <b>80% of your "
            "selection chance</b>.",
            body,
        )
    )
    s.append(
        Paragraph(
            "<b>The good news:</b> most candidates fumble — too long, too rambly, too much code on screen. Nail the "
            "discipline of the 3-minute window and you are in the top 10% by default.",
            body,
        )
    )
    s.append(
        Paragraph(
            "<b>The bad news:</b> there are no second takes once submitted. So practise three full runs, then record on the fourth.",
            body,
        )
    )

    # ---- SECTION 2 ----
    s.append(Paragraph("2. The six winning principles", h1_style))
    principles = [
        ("Decisions, not data.",
         "<i>Sellers do not have a data problem. They have a decision problem.</i> "
         "This is your hook. Land it in the first 30 seconds."),
        ("Show, do not explain code.",
         "Reviewers will read your repo if they like the demo. Talking about code in the video is a wasted second."),
        ("Specificity beats generality.",
         "&quot;Priority 91&quot; beats &quot;high priority.&quot; &quot;Three real APIs&quot; beats "
         "&quot;multiple integrations.&quot; &quot;$4,150 ad spend with collapsing conversion&quot; "
         "beats &quot;a competitor problem.&quot;"),
        ("End with vision, not apology.",
         "&quot;If I had more time&quot; is your last impression. Make it forward-looking, never apologetic."),
        ("Energy carries the screen.",
         "Smile during the intro. Speak 10% slower than feels natural. Look at the camera lens, not the preview window."),
        ("Pause on impact lines.",
         "After &quot;decisions, not data,&quot; pause for half a second. The line earns the silence."),
    ]
    for n, (head, txt) in enumerate(principles, 1):
        s.append(Paragraph(f"<b>{n}. {head}</b> {txt}", body))

    s.append(PageBreak())

    # ---- SECTION 3 — STRUCTURE TABLE ----
    s.append(Paragraph("3. The 3-minute structure", h1_style))
    s.append(
        Paragraph(
            "Memorise the section transitions. The total comes to about 405 spoken words at a calm pace — fits in 175 to 180 seconds, leaving buffer.",
            body,
        )
    )
    structure = [
        ["Time", "Section", "Camera shows", "What you say"],
        ["0:00 – 0:25", "Intro + hook", "Your face", "Identity + the one-liner thesis"],
        ["0:25 – 0:45", "The problem", "Face → screen", "Why every Amazon tool fails today"],
        ["0:45 – 2:10", "Live demo", "App + voiceover", "Login → 3 cards → click OK"],
        ["2:10 – 2:30", "Why this design", "Face or screen", "Pixii's data is the moat"],
        ["2:30 – 2:50", "APIs / tools", "Screen", "Name 4 APIs, mention 3 are agentic"],
        ["2:50 – 2:58", "More time", "Your face", "One forward vision"],
        ["2:58 – 3:00", "Sign-off", "Your face", "&quot;Thank you.&quot;"],
    ]
    structure_para = [[Paragraph(c, body) for c in row] for row in structure]
    s.append(make_table(structure_para, [0.95 * inch, 1.1 * inch, 1.6 * inch, 2.85 * inch]))

    s.append(PageBreak())

    # ---- SECTION 4 — VERBATIM SCRIPT ----
    s.append(Paragraph("4. The verbatim script", h1_style))
    s.append(
        Paragraph(
            "Read aloud five times. Memorise the first and last sentences cold. Use the rest as anchors during the demo.",
            body,
        )
    )

    s.append(Paragraph("[0:00 – 0:25] Intro + hook", h2_style))
    s.append(
        Paragraph(
            "Hi, I am <b>[YOUR NAME]</b>, [YEAR] year at <b>[YOUR SCHOOL]</b>, CGPA <b>[YOUR CGPA]</b>. "
            "My favourite accomplishment so far? <b>[ONE SENTENCE — see ideas below].</b><br/><br/>"
            "What I am showing you is <b>Pixii Pulse</b> — a feature I built that does not give Amazon sellers data. "
            "It gives them <b>decisions. Already made.</b>",
            script_style,
        )
    )
    s.append(
        Paragraph(
            "<i>Switch to screen-share. Pause for half a second.</i>",
            body_soft,
        )
    )

    s.append(Paragraph("Accomplishment ideas — pick ONE, keep it brief and concrete:", h2_style))
    s.append(
        Paragraph(
            "• Leading my school's [robotics / coding / debate] team to nationals in 2024.<br/>"
            "• Shipping my first product — a [thing] used by [N] users.<br/>"
            "• Won the [X] competition last year by [Y].<br/>"
            "• Built and deployed [project] that solved [specific problem].<br/>"
            "<i>Avoid vague ones like &quot;my growth&quot; or &quot;learning to code.&quot; "
            "Pick a verb plus a number if possible.</i>",
            body,
        )
    )

    s.append(Paragraph("[0:25 – 0:45] The problem", h2_style))
    s.append(
        Paragraph(
            "Every Amazon tool today shows the seller charts and asks them to decide what to do. "
            "Helium 10. Jungle Scout. DataHawk. They are all dashboards.<br/><br/>"
            "Pixii Pulse flips it. The seller wakes up to <b>three actions, already decided, already written</b>. "
            "Their job is OK or Deny.",
            script_style,
        )
    )

    s.append(PageBreak())

    s.append(Paragraph("[0:45 – 2:10] Live demo", h2_style))
    s.append(
        Paragraph(
            "Here is the seller logged in as <b>PrimeBrands Co.</b>. Pixii Pulse picked their resistance bands today — "
            "priority 91. The reason: a competitor dropped price 15% overnight, ad spend is up, but conversion is collapsing. "
            "I click <b>Generate Today's Briefing</b>.",
            script_style,
        )
    )
    s.append(
        Paragraph(
            "<i>Click Generate. Wait for the pipeline (~5 sec). Do not fill the silence — let the spinner run, it shows the system working.</i>",
            body_soft,
        )
    )
    s.append(
        Paragraph(
            "First thing the agent does — it calls three real tools. Pulled the competitor's Amazon listing. "
            "Checked Google Trends for &quot;snap-proof&quot; demand. Searched Reddit for outside-Amazon mentions. "
            "<b>The LLM decided which to call.</b><br/><br/>"
            "Three priority cards.<br/><br/>"
            "<b>Card one: review reply.</b> The seller has 13 customer complaints about bands snapping. "
            "Pixii Pulse drafted a public reply offering a free reinforced replacement. I click OK — "
            "in production this publishes via Amazon's SP-API.<br/><br/>"
            "<b>Card two: listing rewrite.</b> Five missing keywords competitors are using. "
            "Pixii Pulse wrote a new bullet that includes them all naturally.<br/><br/>"
            "<b>Card three: pricing.</b> Pixii Pulse called the live currency exchange API — "
            "found that the UK marketplace is 28 percent above the seller's USD-equivalent median. "
            "Recommends dropping the UK price to recover sales.<br/><br/>"
            "Three decisions. Three deliverables. <b>The seller's day, in two minutes.</b>",
            script_style,
        )
    )
    s.append(
        Paragraph(
            "<i>Hover over a Pulse Score (e.g. 700) and briefly expand &quot;Why this priority?&quot;</i>",
            body_soft,
        )
    )
    s.append(
        Paragraph(
            "Each card has a Pulse Score — Severity times Frequency times Revenue Impact, max 1000. "
            "The seller can see exactly why this ranked above the others.",
            script_style,
        )
    )

    s.append(Paragraph("[2:10 – 2:30] Why this design", h2_style))
    s.append(
        Paragraph(
            "Why this design? Pixii already has the seller's catalog and conversion data. The seller should not "
            "have to paste URLs or dig through 50 reviews — the data is already there.<br/><br/>"
            "<b>The seller is the safety check, not the work-doer.</b> Pixii Pulse drafts; the seller verifies and ships.",
            script_style,
        )
    )

    s.append(Paragraph("[2:30 – 2:50] APIs and tools", h2_style))
    s.append(
        Paragraph(
            "Beyond the LLM, Pixii Pulse uses <b>four real external APIs</b>:<br/><br/>"
            "Amazon listing scraping. Google Trends. Reddit search. And Open Exchange Rates for cross-marketplace pricing.<br/><br/>"
            "<b>Three of those are wrapped as agentic tools</b> — the LLM picks which to call. The fourth — currency rates — "
            "is the analyst calculating USD-equivalent prices directly.",
            script_style,
        )
    )

    s.append(Paragraph("[2:50 – 2:58] If I had more time", h2_style))
    s.append(
        Paragraph(
            "With more time, I would wire the OK button to Amazon's SP-API so it actually publishes the changes — "
            "<b>closing the loop between recommendation and execution</b>. And I would add per-seller voice memory, "
            "so every output sounds like the seller's brand, not generic AI.",
            script_style,
        )
    )

    s.append(Paragraph("[2:58 – 3:00] Sign-off", h2_style))
    s.append(Paragraph("<b>Thank you.</b>", script_style))
    s.append(
        Paragraph(
            "<i>Smile. Hold for one second. Stop the recording.</i>",
            body_soft,
        )
    )

    s.append(PageBreak())

    # ---- SECTION 5 — what to show ----
    s.append(Paragraph("5. What to show on screen, moment by moment", h1_style))
    show_data = [
        ["Seconds", "Screen", "Action"],
        ["0:00 – 0:25", "Camera only — your face",
         "Do not share screen yet. Make eye contact with the lens."],
        ["0:25 – 0:35", "Camera, switching to app",
         "Bring browser forward. Pixii Pulse login screen visible."],
        ["0:35 – 0:45", "App login screen",
         "Type password (or be pre-logged in). Press Enter."],
        ["0:45 – 1:00", "Daily Actions page (top)",
         "Auto-pick panel: PB-RES-05, priority 91, three metrics."],
        ["1:00 – 1:15", "Click Generate; spinner",
         "Spinner cycles through scan / investigator / analyse / decide / execute."],
        ["1:15 – 1:30", "Investigator panel (auto-expanded)",
         "Read agent's research summary. Mention &quot;3 tools&quot;."],
        ["1:30 – 1:50", "Card 1 — REVIEW",
         "Read issue + output. Click OK. Card turns green."],
        ["1:50 – 2:00", "Cards 2 and 3",
         "Show listing rewrite text + pricing recommendation."],
        ["2:00 – 2:10", "&quot;Why this priority?&quot; expander",
         "Show 4 metrics breakdown briefly."],
        ["2:10 – 2:30", "Camera (your face)",
         "&quot;Why this design&quot; — be present."],
        ["2:30 – 2:50", "Investigator panel scrolled into view",
         "Point to the 3 tool calls."],
        ["2:50 – 3:00", "Camera",
         "Final &quot;more time&quot; + thank you."],
    ]
    show_para = [[Paragraph(c, body) for c in row] for row in show_data]
    s.append(make_table(show_para, [0.95 * inch, 1.85 * inch, 3.7 * inch]))

    s.append(PageBreak())

    # ---- SECTION 6 — phrases that win ----
    s.append(Paragraph("6. What makes you unique — phrases to drop", h1_style))
    s.append(Paragraph("Most candidates will not say these. Drop at least three:", body))
    phrases = [
        "&quot;Decisions, not data.&quot; (your North Star)",
        "&quot;Pixii Pulse does not ask. It already knows.&quot;",
        "&quot;The seller is the safety check, not the work-doer.&quot;",
        "&quot;Three decisions. Three deliverables. Two minutes.&quot;",
        "&quot;Closing the loop between recommendation and execution.&quot;",
        "&quot;OK or Deny — the entire seller interaction.&quot;",
        "&quot;The LLM decided which tools to call.&quot;",
        "&quot;Pixii's data is the moat.&quot;",
    ]
    for p in phrases:
        s.append(Paragraph(f"• {p}", checklist_style))

    s.append(Spacer(1, 8))
    s.append(Paragraph("Phrases to avoid (generic AI talk):", h2_style))
    avoids = [
        "leverage AI to...",
        "powered by cutting-edge LLMs",
        "intelligent assistant",
        "personalised insights",
        "revolutionary AI-driven solution",
    ]
    for p in avoids:
        s.append(Paragraph(f"✗ {p}", checklist_style))

    # ---- SECTION 7 — checklist ----
    s.append(Paragraph("7. Pre-recording checklist", h1_style))

    s.append(Paragraph("Equipment", h2_style))
    eq = [
        "Phone or webcam at eye level (not below — angle matters).",
        "Decent microphone (built-in laptop mic is OK; a $20 USB mic is better).",
        "Light source in <b>front</b> of you (window or lamp), never behind.",
        "Quiet room — close door, mute notifications, airplane mode the phone.",
        "Camera ON for the whole video. <b>Camera-off submissions are disqualified.</b>",
    ]
    for x in eq:
        s.append(Paragraph(f"☐ {x}", checklist_style))

    s.append(Paragraph("App state before recording", h2_style))
    appst = [
        "<b>streamlit run app.py</b> is running and the URL is open.",
        "Logged in (or password ready to type fast).",
        "On the Daily Actions page; default SKU is PB-RES-05 (priority 91).",
        "Internet is stable — re-test the Generate button right before recording.",
        "Browser zoom 110-125% so text reads on screen-share.",
        "All other tabs closed. Notifications muted.",
        "Theme is dark (looks more polished on a recording).",
    ]
    for x in appst:
        s.append(Paragraph(f"☐ {x}", checklist_style))

    s.append(Paragraph("Personal", h2_style))
    pers = [
        "Three full practice runs without stopping.",
        "Timed at least one practice — under 3:00.",
        "Anchors only — not reading from a script.",
        "Well-rested, energetic. Record in the morning if possible.",
        "Bottle of water nearby in case voice cracks.",
        "Wearing solid colour (avoid busy patterns on camera).",
    ]
    for x in pers:
        s.append(Paragraph(f"☐ {x}", checklist_style))

    s.append(PageBreak())

    # ---- SECTION 8 — DOs / DON'Ts ----
    s.append(Paragraph("8. Recording — do's and don'ts", h1_style))

    do_dont_data = [
        ["DO", "DON'T"],
        ["Record in one take. Cuts look amateur.",
         "Open VS Code or any code editor on screen."],
        ["Smile during the intro. It is contagious.",
         "Read line by line from a script."],
        ["Pause briefly after impact lines.",
         "Apologise (&quot;sorry the demo is glitchy&quot; — pre-test)."],
        ["Speak 10% slower than feels natural.",
         "Say &quot;um&quot;, &quot;kind of&quot;, &quot;just a small thing&quot;."],
        ["Look at the camera lens during personal sections.",
         "Go over 3 minutes — they will dock you."],
        ["Show the screen during the demo, your face during personal/why.",
         "End with a question (&quot;any feedback?&quot;). End decisive."],
        ["Wear something solid-coloured.",
         "Mention specific LLM brands by name. Say &quot;the LLM&quot; or &quot;the AI agent&quot;."],
    ]
    do_dont_para = [[Paragraph(c, body) for c in row] for row in do_dont_data]
    s.append(make_table(do_dont_para, [3.25 * inch, 3.25 * inch]))

    # ---- SECTION 9 — final tweaks ----
    s.append(Paragraph("9. Five subtle tweaks that win", h1_style))
    tweaks = [
        ("Open with energy, not throat-clearing.",
         "Skip &quot;Hello hello, can you hear me?&quot; Just go."),
        ("Drop one number very early.",
         "&quot;Priority 91&quot; or &quot;five missing keywords&quot; in the first minute anchors you as someone who works with specifics."),
        ("Name the moat once.",
         "<i>&quot;Pixii already has the seller's catalog and conversion data.&quot;</i> "
         "That sentence shows you understand their business."),
        ("End with what is NEXT, not what is DONE.",
         "&quot;With more time I would wire the OK button to SP-API…&quot; That tells the reviewer you would keep building. "
         "The ones they hire are the ones who never feel finished."),
        ("Sign off with one word.",
         "&quot;Thank you.&quot; Not &quot;thanks for watching, hope you enjoyed it, please consider me.&quot; "
         "One word. Hold the camera. Stop."),
    ]
    for n, (head, txt) in enumerate(tweaks, 1):
        s.append(Paragraph(f"<b>{n}. {head}</b> {txt}", body))

    # ---- SECTION 10 — after recording ----
    s.append(Paragraph("10. After the recording", h1_style))
    after = [
        "Watch your video back once, all the way through.",
        "Time it. If it is over 3:05, re-record.",
        "If audio is muddy, re-record with a closer mic.",
        "Upload to YouTube as <b>unlisted</b> (not public, not private — unlisted) so Pixii can watch via link.",
        "Submit the link in the form, alongside your repo URL.",
        "Don't watch your video 50 times. Submit it. Move on.",
    ]
    for x in after:
        s.append(Paragraph(f"☐ {x}", checklist_style))

    s.append(Paragraph("11. The README hook (matches the video)", h1_style))
    s.append(
        Paragraph(
            "Reviewers who like the video will open your GitHub. The first line of your README should mirror the video's hook:",
            body,
        )
    )
    s.append(
        Paragraph(
            "<b>Pixii Pulse — Three Amazon decisions every morning. Already made. Already written.</b>",
            quote_style,
        )
    )
    s.append(
        Paragraph(
            "Pin that as line one. Everything else (setup, architecture, walkthrough) goes underneath.",
            body,
        )
    )

    # ---- closing ----
    s.append(Spacer(1, 18))
    s.append(hr())
    s.append(
        Paragraph(
            "<i>Three minutes. One take. The story you have built is genuinely strong — "
            "your job in the recording is to get out of its way. Good luck.</i>",
            body_soft,
        )
    )

    return s


def main():
    doc = SimpleDocTemplate(
        str(OUT_PATH),
        pagesize=LETTER,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.6 * inch,
        title="Pixii Pulse — Submission Video Guide",
        author="Pixii Pulse",
    )
    doc.build(build_story(), onFirstPage=page_decoration, onLaterPages=page_decoration)
    print(f"Wrote: {OUT_PATH}")


if __name__ == "__main__":
    main()
