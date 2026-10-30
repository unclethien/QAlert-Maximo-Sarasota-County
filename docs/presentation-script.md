# Presentation script: Sprint 2 sample dataset

A speaker script for the 11-slide deck in [`presentation/`](../presentation). It runs about 10 minutes for a mixed audience of the IBM team and Sarasota County staff. Read it as written, or use it as talking points.

## Before you present

The deck is online at https://unclethien.github.io/QAlert-Maximo-Sarasota-County/. Open it in your browser and press **F** for full screen. Nothing to install.

To run it from your own laptop instead, for example without internet:

```bash
cd presentation
npm install        # first time only
npm run dev        # opens on http://localhost:5180
```

Then open http://localhost:5180 and press **F**.

- **Next slide:** right arrow, down arrow, Space, Enter, or Page Down (most presentation clickers send Page Down).
- **Previous slide:** left arrow, up arrow, Backspace, or Page Up.
- **First or last slide:** Home or End.

The slide number is in the address (for example `#/5`), so you can jump straight to a slide.

The numbers on the slides are read from the files in `data/`. If the dataset is regenerated, the slides update on their own; check that the numbers in this script still match.

---

## 1. A practice dataset for the Sarasota AI pilot (about 30 seconds)

**On screen:** the title, and the line "Entered by: 0821106" highlighted in orange.

**Say:**

> Thanks for joining. Today I'll walk you through the sample dataset we built in Sprint 2 for the MAS AI pilot.
>
> It's practice data. Nothing in it comes from real County records. We built it so we can test whether the AI catches the problems we care about, before we ever point it at real requests.
>
> Keep an eye on that orange line at the bottom right. It's the one small change this whole dataset is built around, and we'll come back to it.

## 2. Today, Maximo loses who took the call (about 1 minute)

**On screen:** service request SR800001 as Maximo shows it today.

**Say:**

> This is what a request looks like in Maximo today, after it comes over from QAlert.
>
> First, "Reported by" always says "QAlert Integration". That's the system account, not the person who took the call.
>
> Second, everything else, the caller, the address, and the problem, is packed into one text field.
>
> So when something's missing, like here where there's a street name but no house number, nobody in Maximo can tell who to ask. Staff have to go back into QAlert, find the same request, and work out who entered it. That's the gap this pilot is trying to close.

## 3. 60 requests, four kinds of test (about 45 seconds)

**On screen:** one bar split into four groups: 24, 15, 9, and 12.

**Say:**

> The dataset has 60 service requests, and each one was written on purpose to test one thing.
>
> 24 are missing information: no address, too little detail, or the wrong request type.
>
> 15 are about duplicates, where several people call about the same problem.
>
> 9 have related past or planned work at the same place.
>
> And 12 are complete requests with nothing wrong. Those matter too: they check that the AI doesn't raise false alarms.

## 4. Two systems, linked like the real ones (about 45 seconds)

**On screen:** three columns of counts: Maximo, QAlert, and "Also included".

**Say:**

> Here's what's in the dataset. On the Maximo side: 60 service requests, 41 work orders, 125 work log notes, and 18 person records.
>
> On the QAlert side, which is our mock: the 60 matching requests, 139 history entries, and 15 staff members who enter requests.
>
> We also added a stand-in for the County's address list, with 236 points, so we can test whether an address is real. And an answer key, which I'll show you in a minute.
>
> Everything here is made up: names, phone numbers, emails, and street names. Only the city names and ZIP codes are real, so the addresses look local.

## 5. One extra line connects the two (about 1 minute 15 seconds)

**On screen:** the request details with "Entered by: 0821106" highlighted, an arrow, and Linda Chen's QAlert staff record.

**Say:**

> This is the key idea. We add one line to the bottom of each request: "Entered by", followed by the employee ID of the staff member who took the call.
>
> With that ID, the AI can look the person up in QAlert. Here it's Linda Chen in the Contact Center, with her phone and email. Now there's a real person to ask.
>
> We also built in the harder cases on purpose. 6 of the 15 QAlert staff have no person record in Maximo, so their contact details can only come from QAlert. And 2 are no longer active, so the AI should send the question to the supervisor instead.
>
> I want to be clear that this is our assumption about how the ID could come across. We need your help to confirm it, and I'll come back to that at the end.

## 6. 24 requests are missing something (about 1 minute)

**On screen:** seven bars, one for each kind of missing information, and the number 8 in orange.

**Say:**

> Let's look at the biggest group. The 24 missing-information requests fall into seven patterns: no usable address, too little detail, the wrong request type, an address that doesn't exist, unclear what's wrong, two problems in one request, and problems that are likely private plumbing.
>
> The example under each bar is the kind of thing the AI should notice.
>
> And look at the 8 on the left. In 8 of these, a crew had already been sent out. In real life those are trips that one phone call could have saved. That's the value we're after.

## 7. What the AI should do with SR800001 (about 1 minute)

**On screen:** four steps: spot the gap, find who entered it, ask one question, then dispatch.

**Say:**

> Here's what we expect the AI to do with that first request, step by step.
>
> One: spot the gap. There's a street, but no house number.
>
> Two: find who entered it. The "Entered by" line points to Linda Chen in the Contact Center.
>
> Three: suggest one clear question for her to ask the caller: can they give the house number, or describe the closest house to the leak?
>
> Four: only then send a crew.
>
> The AI doesn't change the request itself. It gives staff a recommendation they can act on.

## 8. Three calls, one outage (about 1 minute)

**On screen:** a timeline of October 21, with three calls at 6:40, 7:58, and 9:11 AM on Bramblewick Lane.

**Say:**

> Now duplicates. On the morning of October 21, three households on Bramblewick Lane called within about two and a half hours.
>
> The first two came in as "No Water". The third was filed as "Low Water Pressure", but it's the same outage.
>
> The AI should spot that these belong together and suggest linking the second and third requests to the first, instead of sending three crews.
>
> Overall the dataset has five groups like this. It also has three look-alikes: requests on the same street or the same night that are actually different problems. The AI should not link those.

## 9. Some places already have history (about 1 minute)

**On screen:** past work at 1382 Larkspur Bay Drive, and a planned project on Starling Cove Drive.

**Say:**

> The third use case is history.
>
> On the left, 1382 Larkspur Bay Drive. There was a service line leak in February, another in July, and a new leak reported in September. That's the third in a year, so the AI should point that out. It's probably more than a quick repair.
>
> On the right, Starling Cove Drive. A water main replacement is scheduled from November 16 to December 18. When a new request comes in on that street, the AI should point to the project rather than open separate repair work.

## 10. An answer key for every request (about 45 seconds)

**On screen:** a table of five sample rows from the answer key.

**Say:**

> To check the AI, we wrote down the right answer for every one of the 60 requests: what it should flag, who to contact, and which other records are related.
>
> When the AI runs on this data, we compare what it says against this file, one request at a time. That gives us a clear, honest score instead of a gut feeling.
>
> The last row is a complete request. There the right answer is "nothing to flag".

## 11. Please check these assumptions (about 1 minute 15 seconds)

**On screen:** four assumptions with checkboxes, and the next steps.

**Say:**

> This is where we need your help. The dataset is built on our assumptions, and we need you to confirm or correct them:
>
> - Do QAlert and Maximo use the same employee ID?
> - Is it true that only County staff enter requests in QAlert?
> - Could the employee ID come across as an "Entered by" line, or is there a better place for it?
> - Can QAlert give us each staff member's name, phone, email, and department?
>
> Next, we'll build a mock QAlert service and its API guide, so the AI can look people up the way it would in production.
>
> Two open questions for the group: where should that mock service run, and what can the real QAlert API return, and how do we get access?
>
> Everything I showed is in the GitHub repository on the slide. If anything looks wrong, send me the file name, the request number, and what you'd expect instead. Thank you.

---

**Total:** about 10 minutes, plus questions.
