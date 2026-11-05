# Presentation script: Sprint 2 sample dataset

A speaker script for the 14-slide deck in [`presentation/`](../presentation). It runs about 12 minutes for a mixed audience of the IBM team and Sarasota County staff. Read it as written, or use it as talking points.

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

**On screen:** the title, and request SR800001 with "Came in through the 311Connect mobile app" highlighted in orange.

**Say:**

> Thanks for joining. Today I'll walk you through the sample dataset we built in Sprint 2 for the MAS AI pilot.
>
> It's practice data. Nothing in it comes from real County records. We built it so we can test whether the AI catches the problems we care about, before we ever point it at real requests.
>
> Keep an eye on that orange line at the bottom right. Where a request came from turns out to decide who the AI should ask, and we'll come back to it.

## 2. Today, Maximo can't tell who to ask (about 45 seconds)

**On screen:** service request SR800001 as Maximo shows it today, with three notes on the right.

**Say:**

> This is what a request looks like in Maximo today, after it comes over from QAlert.
>
> "Reported by" always says "QAlert Integration". That's the system account, not a person.
>
> Nothing in Maximo says whether the request came from the app, the web portal, or a call to 311. The resident's name and contact details are packed into one text field with everything else.
>
> So when something's missing, like here where there's a street name but no house number, staff have to go back into QAlert and find the same request to work out who to ask. That's the gap this pilot is trying to close.

## 3. Most requests come from residents (about 1 minute)

**On screen:** one bar split into four channels: 32 from the 311Connect app, 19 from the 311 web portal, 11 phone calls to 311, and 3 emails.

**Say:**

> Sarasota's 311 has four ways in. Residents can use the 311Connect app or the 311 web portal themselves. Or they can call 311, or 941-861-5000 from outside the County, or email the Contact Center, and a staff member enters the request for them.
>
> We've heard that most requests now come in through the app and the website, and only a small share through the Contact Center. So in the dataset, 51 of the 65 requests come straight from residents and 14 were entered by Contact Center staff. That's about one in five.
>
> That split is our assumption, not a measured number. If you have the real figures, we'll adjust.
>
> It matters because it changes who the AI should ask. If the resident sent it, ask the resident. If staff entered it, ask the staff member who took the call or the email.

## 4. 65 requests, four kinds of test (about 40 seconds)

**On screen:** one bar split into four groups: 28, 16, 9, and 12.

**Say:**

> Each of the 65 requests was written on purpose to test one thing.
>
> 28 are missing information or may not be the County's job: no address, too little detail, the wrong request type, or a problem that belongs to a plumber or another utility. 16 are about duplicates, where several people report the same problem. 9 have related past or planned work at the same place.
>
> And 12 are complete requests with nothing wrong. Those check that the AI doesn't raise false alarms.

## 5. Two systems, linked like the real ones (about 40 seconds)

**On screen:** three columns of counts: Maximo, QAlert, and "Also included".

**Say:**

> On the Maximo side: 65 service requests, 41 work orders, 127 work log notes, and 18 person records.
>
> On the QAlert side, which is our mock: the 65 matching requests, 150 history entries, and 15 Contact Center staff who enter phone and email requests.
>
> We also added a stand-in for the County's address list, with 244 points, so we can test whether an address is real and who supplies its water. And an answer key, which I'll show you in a minute.
>
> Everything is made up: names, phone numbers, emails, and street names. Only the city names and ZIP codes are real, so the addresses look local.

## 6. Where it came from decides who to ask (about 1 minute 15 seconds)

**On screen:** two requests side by side with who to ask. SR800001 came from the app, so ask the resident, Theresa Sheffield. SR800008 was a phone call, with "Entered by: 0820533", so ask Daniel Okafor in the Contact Center.

**Say:**

> This is the key idea. The AI looks up the request in QAlert, which records where it came from.
>
> In the top example, the resident sent it through the 311Connect app. Their name, phone, and email are already in the request, so the AI suggests contacting them directly.
>
> In the bottom example, someone called 311. For staff-entered requests only, we add one line: "Entered by", followed by the employee ID. With that ID, the AI finds Daniel Okafor in the Contact Center, the person who took the call. He has no person record in Maximo, so his details come from QAlert.
>
> We built in the harder cases on purpose: 6 staff with no Maximo record, 2 who are no longer active, so the question goes to their supervisor, and one anonymous web request with no contact details at all, which goes to the crew's supervisor.
>
> The "Entered by" line is our assumption about how the ID could come across. We need your help to confirm it.

## 7. 28 requests are missing something or may not be ours (about 50 seconds)

**On screen:** seven bars, one for each kind of missing information, and the number 8 in orange.

**Say:**

> These 28 requests fall into seven patterns: no usable address, too little detail, the wrong request type, an address that doesn't exist, unclear what's wrong, two problems in one request, and a problem that may not be the County's job. That last group covers private plumbing, a private backflow device, and two addresses that the City of North Port or City of Venice utility serves.
>
> The example under each bar is the kind of thing the AI should notice.
>
> And look at the 8 on the left. In 8 of these, a crew had already been sent out. Those are trips that one question could have saved. That's the value we're after.

## 8. What the AI should do with SR800001 (about 50 seconds)

**On screen:** four steps: spot the gap, check the source, ask one question, then dispatch.

**Say:**

> Here's what we expect the AI to do with that first request.
>
> One: spot the gap. There's a street, but no house number.
>
> Two: check the source. QAlert says it came from the 311Connect app, so the resident can be asked directly.
>
> Three: suggest one clear question: can you give the house number, or describe the closest house to the leak?
>
> Four: only then send a crew.
>
> The AI doesn't change the request itself. It gives staff a recommendation they can act on.

## 9. Three reports, one outage (about 50 seconds)

**On screen:** a timeline of October 21, with three reports at 6:40, 7:58, and 9:11 AM on Bramblewick Lane.

**Say:**

> Now duplicates. On the morning of October 21, three households on Bramblewick Lane reported a problem within about two and a half hours.
>
> The first two came in as "No Water". The third was filed as "Low Water Pressure", but it's the same outage.
>
> The AI should suggest linking the second and third requests to the first, instead of sending three crews.
>
> Overall there are five groups like this, plus four look-alikes the AI should not link. Three are on the same street or the same night but are different problems. The fourth is at the first Bramblewick address itself: water came up again six days after the main was repaired. Because that repair was finished, it's new work, not a duplicate.

## 10. Some places already have history (about 50 seconds)

**On screen:** past work at 1382 Larkspur Bay Drive, and a planned project on Starling Cove Drive.

**Say:**

> The third use case is history.
>
> On the left, 1382 Larkspur Bay Drive. A service line leak in February, another in July, and a new leak reported in September. That's the third in a year, so the AI should point that out. It's probably more than a quick repair.
>
> On the right, Starling Cove Drive. A water main replacement is scheduled from November 16 to December 18. When a new request comes in on that street, the AI should point to the project rather than open separate repair work.

## 11. Requests arrive with no team (about 50 seconds)

**On screen:** SR800024 with a blank team, the team the AI suggests, then work order WO2900020 with job plan LEAK, team WTRPIPE, and its crew lead and supervisor.

**Say:**

> One more thing the AI can help with: who does the work.
>
> At the top is a request as it arrives in Maximo: a water line leak at 1984 Ashcombe Drive. The team field is blank. In Sarasota, the team isn't on the request. It's set later, on the work order.
>
> Today a person decides which crew gets it. We want the AI to suggest the team, here the water distribution pipe crew, WTRPIPE, and a planner approves it.
>
> At the bottom is what happens next. The planner applies a job plan, here LEAK, and the job plan fills in the team, the supervisor, and the crew lead on the work order.
>
> The answer key records the right team for 60 of the 65 requests. The other five aren't County Utilities work: two drainage requests for Public Works, a private backflow device, and two addresses that a city utility serves.

## 12. An answer key for every request (about 40 seconds)

**On screen:** a table of five sample rows from the answer key, including who to contact and why.

**Say:**

> To check the AI, we wrote down the right answer for every one of the 65 requests: what it should flag, who to contact, and which other records are related.
>
> Notice the contact column. For app and web requests it's the resident. For phone and email requests it's the staff member who took it.
>
> When the AI runs on this data, we compare what it says against this file, one request at a time. That gives us a clear, honest score instead of a gut feeling.

## 13. What changed after IBM's data review (about 1 minute)

**On screen:** four numbers: 6 requests that may not be the County's job, 1 request rerouted without a crew, 15 required-information rules, and 1 repeat at the same address that is not a duplicate.

**Say:**

> IBM's updated review of the County's examples showed four gaps in our test data, so we closed them. Every request from before keeps its number and details.
>
> First, 6 requests that may not be the County's job: private plumbing inside the home, a private backflow device, and two addresses served by the City of North Port or City of Venice utility. The AI should check whose job it is and say who to refer the customer to.
>
> Second, a request filed as a sewer issue that is really clogged storm drains. As in your misrouted examples, it's closed with a note to the Contact Center, and no crew goes out.
>
> Third, 15 rules for what each request type must include before a crew goes out, such as a findable address, or the symptom for a sewer problem. The incomplete requests now say which rules they break. These rules are our proposal, so please correct them.
>
> And fourth, water comes back at an address six days after the repair was finished. That's new work, not a duplicate of an open request.
>
> With these, our scenarios match your five example groups: duplicates, similar but not duplicate, incomplete, misrouted, and not the County's job.

## 14. Please check these assumptions (about 1 minute 10 seconds)

**On screen:** five assumptions with checkboxes, and the next steps.

**Say:**

> This is where we need your help. The dataset is built on our assumptions, and we need you to confirm or correct them:
>
> - Is it right that most requests come from residents through the app and web portal, and about one in five through the Contact Center?
> - Does QAlert record where each request came from, and who entered phone and email requests?
> - Do QAlert and Maximo share the employee ID, and could it come across as an "Entered by" line?
> - The labels we use for where a request came from are placeholders. What does QAlert actually call them?
> - Which streets the North Port and Venice utilities serve, and what each request type must include, are our placeholders too. Please correct them.
>
> Next, we'll build a mock QAlert service and its API guide, so the AI can look up requests and people the way it would in production.
>
> Two open questions for the group: where should that mock service run, and what can the real QAlert API return, and how do we get access?
>
> Everything I showed is in the GitHub repository on the slide. If anything looks wrong, send me the file name, the request number, and what you'd expect instead. Thank you.

---

**Total:** about 12 minutes, plus questions.
