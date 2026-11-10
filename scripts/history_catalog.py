"""Reference data for the synthetic training history behind the MAS AI pilot.

The history is a set of past, closed requests that Maximo's field value recommendation model learns
from. The 65 pilot SRs are what the model is tested on, so the history shares no IDs, streets,
residents or wording with them. Every name, street and sentence here is invented.
"""

HISTORY_SEED = 20261106
PER_CLASS = 90  # SRs per classification. The mcc template asks watsonx.ai for extra examples of any value with fewer than 50 training records (its training split is about two thirds), and that step fails on TechZone, so every value gets enough to skip it.

# History dates end the day before the pilot window starts, so a REPORTDATE filter separates them.
HISTORY_START = "2024-08-01"
HISTORY_END = "2026-07-31"

# ID ranges below the pilot's (SR800001, request 700001, WO2900001, work log 3000001).
SR_START, REQUEST_START, WO_START, WORKLOG_START = 600001, 500001, 2700001, 3500001

# A share of requests arrive under the wrong QAlert type, and the planner corrects the
# classification before closing. The description keeps the type the resident picked, so the model
# has to read the text, not copy the type name. (true type, types it gets filed under)
MISFILE_SHARE = 0.12
CONFUSABLE = {
    "Water Line Leak": ("Water Main Break", "Curb Stop", "Water Meter Issue"),
    "Water Main Break": ("Water Line Leak",),
    "Low Water Pressure": ("No Water",),
    "No Water": ("Low Water Pressure", "Water Line Leak"),
    "Water Meter Issue": ("Water Line Leak", "Curb Stop"),
    "Curb Stop": ("Water Meter Issue", "Water Line Leak"),
    "Backflow Device Issue": ("Water Line Leak", "Water Meter Issue"),
    "Sewer Issue": ("Sewer Odor",),
    "Sewer Odor": ("Sewer Issue",),
    "Lift Station Alarm": ("Sewer Issue", "Sewer Odor"),
    "Force Main Break": ("Water Main Break", "Sewer Issue"),
    "Reclaimed Water Issue": ("Water Line Leak", "Low Water Pressure"),
}
# Stormwater requests reach Utilities only by mistake, so every one is filed under a Utilities type.
STORMWATER_FILED_AS = ("Water Line Leak", "Sewer Issue", "Water Main Break")

# Streets used only by the history. None appears in the pilot catalog.
STREETS = [
    ("Amberjack Hollow Dr", "Sarasota"), ("Brightwater Fern Ln", "Sarasota"), ("Cobalt Heron Way", "Sarasota"),
    ("Dunesparrow Ct", "Sarasota"), ("Egret Lantern Ave", "Sarasota"), ("Foxtail Palm Rd", "Sarasota"),
    ("Goldenrain Cir", "Sarasota"), ("Harborlight Ter", "Sarasota"), ("Indigo Sedge Ln", "Sarasota"),
    ("Jacaranda Loop Dr", "Sarasota"), ("Kingsnake Run Way", "Sarasota"), ("Lanternfish Ct", "Sarasota"),
    ("Mangrove Echo Rd", "Venice"), ("Nautilus Grove Ave", "Venice"), ("Oleander Reach Dr", "Venice"),
    ("Pelican Shoal Ln", "Venice"), ("Quillback Ct", "Venice"), ("Riverbirch Path", "Nokomis"),
    ("Saltmeadow Way", "Nokomis"), ("Tarpon Vista Dr", "Nokomis"), ("Umbrella Pine Ct", "Osprey"),
    ("Vireo Hammock Rd", "Osprey"), ("Wrenfield Ave", "North Port"), ("Yellowfin Trace", "North Port"),
    ("Arrowroot Bluff Ln", "North Port"), ("Blue Marlin Ct", "North Port"), ("Cypress Ember Dr", "Englewood"),
    ("Dolphin Crest Ave", "Englewood"), ("Estuary Gate Rd", "Englewood"), ("Firebush Ln", "Englewood"),
]

# Resident name pools, distinct from the pilot's.
FIRST_NAMES = [
    "Adrienne", "Bernard", "Celeste", "Dorian", "Estelle", "Fletcher", "Georgina", "Hollis",
    "Imogen", "Julian", "Katrina", "Lionel", "Marisol", "Nolan", "Ophelia", "Percy",
    "Raquel", "Silas", "Tabitha", "Ulysses", "Verity", "Warren", "Ximena", "Yusuf", "Zelda",
]
LAST_NAMES = [
    "Achterberg", "Blackwood", "Corrigan", "Dashwood", "Eberhardt", "Fitzwilliam", "Grantham",
    "Halvorsen", "Iverson", "Jablonski", "Kincaid", "Lockhart", "Montague", "Nakashima",
    "Okonkwo", "Prescott", "Radcliffe", "Stavros", "Tremaine", "Vasquez-Hale",
]

# What residents write, by true request type. A request combines one symptom with an optional
# detail and an optional time cue, so the same meaning appears in many wordings.
SYMPTOMS = {
    "Water Line Leak": [
        "Water is bubbling up in my front yard near the sidewalk",
        "There is a wet spot in the grass by the meter that never dries out",
        "Clean water keeps running down the gutter from under the driveway",
        "The ground near my water line is soggy and I can hear water running",
        "Leak between the meter box and the house, the yard is flooded",
        "Water seeping out of the grass along the property line",
        "pipe leaking in front yard, water running constantly",
        "Small stream of water coming out next to the meter lid",
        "My water bill jumped and there is a puddle by the service line",
    ],
    "Water Main Break": [
        "Water is gushing out of the road in front of my house",
        "Big break in the street, water pouring out of the pavement",
        "The road is cracked and water is shooting up through it",
        "Main break at the intersection, the lane is flooded",
        "Water pushing up through the asphalt and running down the street",
        "Huge amount of water coming out of the road, cars are driving through it",
        "Street is buckling and water is flowing out fast",
        "water main broke, road flooding",
    ],
    "Low Water Pressure": [
        "Water pressure in the whole house is very weak",
        "Shower barely trickles and the sinks are slow too",
        "Pressure dropped a lot, the washing machine takes forever to fill",
        "Very low pressure at every faucet",
        "low pressure all day, hard to run the dishwasher",
        "Water comes out slowly everywhere in the house",
        "The pressure keeps dropping in the evenings, sprinklers will not run",
        "Weak water flow at all taps, neighbors say theirs is weak too",
    ],
    "No Water": [
        "We have no water at all in the house",
        "Turned on the tap and nothing comes out",
        "Water is completely off, no notice was left",
        "No water anywhere in the home since this morning",
        "house has no water, toilets will not refill",
        "Our water stopped completely, the neighbors still have water",
        "Nothing from any faucet, the meter is not moving",
        "Completely out of water, we have small children at home",
    ],
    "Water Meter Issue": [
        "The meter box lid is cracked and someone could trip",
        "The meter display is blank and will not show a reading",
        "My meter is spinning even with everything turned off",
        "The meter box is full of water and the dial is foggy",
        "Meter looks damaged, the glass is broken",
        "meter reading seems wrong, bill is way too high",
        "The lid on my meter box is missing",
        "Meter is buried under dirt and the reader could not find it",
    ],
    "Curb Stop": [
        "The curb stop valve is stuck and will not turn",
        "The shutoff valve at the street is leaking around the stem",
        "Plumber could not close the curb stop, it is seized",
        "The curb valve is broken so we cannot shut off the water",
        "curb stop leaking, water around the valve box",
        "Valve at the curb spins but does not shut the water off",
        "The curb stop box is cracked and the valve is exposed",
        "Need the curb stop fixed, it will not close for our repair",
    ],
    "Backflow Device Issue": [
        "The backflow preventer by my house is spraying water",
        "The backflow device next to the irrigation line is dripping",
        "Backflow assembly is making a loud chattering noise",
        "Water is leaking from the relief valve on the backflow device",
        "backflow preventer cracked after the cold night",
        "The backflow box near the driveway is leaking constantly",
        "Our backflow device is dumping water every few minutes",
        "The test cocks on the backflow device are dripping",
    ],
    "Sewer Issue": [
        "Sewage is backing up into the bathtub",
        "Toilets will not flush and water is coming up in the shower",
        "The cleanout in the yard is overflowing",
        "Sewer backup in the house, all drains are slow",
        "sewage coming out of the cleanout cap",
        "Wastewater is pooling in the yard near the sewer cleanout",
        "Gurgling drains and the toilet backs up when we run the washer",
        "Sewer line seems blocked, the downstairs drains overflow",
    ],
    "Sewer Odor": [
        "Strong sewer smell coming from the manhole in the street",
        "Rotten egg smell around the neighborhood in the evenings",
        "Bad sewer odor near the cleanout outside",
        "The whole block smells like sewage after it rains",
        "sewer smell by the storm drain on the corner",
        "Persistent sewage odor from the manhole cover",
        "There is a foul smell coming from the sewer near the mailboxes",
        "Our yard smells like sewage but nothing is overflowing",
    ],
    "Lift Station Alarm": [
        "The alarm light on the lift station is flashing",
        "Lift station at the end of the street has its horn going off",
        "Red light blinking on the pump station panel",
        "The sewer pump station alarm has been sounding for an hour",
        "lift station alarm beeping nonstop",
        "The lift station near the entrance is making a loud buzzing noise and the light is on",
        "Alarm on the wastewater pump station by the retention pond",
        "Pump station light is flashing and there is a smell",
    ],
    "Force Main Break": [
        "Sewage is spraying out of the ground near the road",
        "Raw sewage bubbling up along the shoulder of the road",
        "Pressurized sewage leak coming up through the grass by the street",
        "There is a sewage geyser near the lift station",
        "sewage pouring out of a pipe break on the main road",
        "Wastewater flowing out of the ground by the canal",
        "The big sewer pipe along the road broke, sewage is running into the ditch",
        "Sewage pushing up through the pavement near the pump station",
    ],
    "Reclaimed Water Issue": [
        "The purple reclaimed pipe in the median is leaking",
        "Reclaimed water is running down the street from the irrigation line",
        "No reclaimed water for our sprinklers this week",
        "Reclaimed line broken, water pooling near the purple valve box",
        "reclaimed irrigation water spraying from the ground",
        "The reclaimed water pressure is too low to run the sprinklers",
        "Purple pipe cracked next to the sidewalk, water bubbling up",
        "Reclaimed valve box is overflowing",
    ],
    "Drainage / Flooding": [
        "The street floods every time it rains and the drain is clogged",
        "Water is standing in the road after the storm and will not drain",
        "The storm drain on the corner is full of leaves and the yard floods",
        "Rainwater is pooling against the house after every storm",
        "ditch is overgrown and the road floods",
        "After heavy rain the culvert backs up and floods the driveway",
        "The swale behind the houses holds water for days after it rains",
        "Storm water is flowing into the garage from the street",
    ],
}
DETAILS = [
    "It is in front of the house.", "It is near the mailbox.", "It is by the driveway.",
    "It is on the side of the house.", "It is across the street.", "It is next to the fire hydrant.",
    "The neighbors noticed it too.", "Please send someone.", "I have photos if needed.",
    "Gate code is not needed.", "The dog is inside so the yard is safe to enter.",
]
TIME_CUES = [
    "Started this morning.", "Since last night.", "It has been going on for two days.",
    "Noticed it an hour ago.", "This has happened before.", "Getting worse every hour.",
    "Started after the work crew left yesterday.",
]

# What the crew writes on the work order, by true request type: (short description, closing notes).
CREW_WORK = {
    "Water Line Leak": ("SERVICE LINE LEAK", ["Excavated and repaired service line leak.", "Replaced leaking meter coupling.",
                                               "Repaired leak on the County side of the meter."]),
    "Water Main Break": ("WATER MAIN BREAK", ["Isolated main, installed repair clamp, restored service.",
                                               "Replaced section of water main. Road patch scheduled."]),
    "Low Water Pressure": ("LOW PRESSURE CHECK", ["Pressure tested at meter, 52 psi. Adjusted pressure reducing valve.",
                                                  "Flushed service line, pressure restored."]),
    "No Water": ("NO WATER", ["Meter valve was closed. Opened valve, service restored.",
                              "Cleared blockage in service line, water restored."]),
    "Water Meter Issue": ("METER REPAIR", ["Replaced damaged meter.", "Replaced cracked meter box lid.",
                                           "Cleaned out meter box, meter reading correctly."]),
    "Curb Stop": ("CURB STOP REPAIR", ["Replaced seized curb stop.", "Repacked curb stop, no further leak."]),
    "Sewer Issue": ("SEWER BACKUP", ["Jetted main line, cleared blockage downstream.",
                                     "Cleared lateral at the cleanout. Advised owner of roots on the private side."]),
    "Sewer Odor": ("SEWER ODOR", ["Inspected manhole, replaced gasket on cover.", "Flushed line and treated for odor."]),
    "Lift Station Alarm": ("LIFT STATION ALARM", ["Reset pump 2, float was stuck. Station running normally.",
                                                  "Cleared rags from pump impeller, alarm cleared."]),
    "Force Main Break": ("FORCE MAIN BREAK", ["Bypassed station, repaired force main, cleaned up spill.",
                                              "Installed repair coupling on force main. Reported spill to state."]),
    "Reclaimed Water Issue": ("RECLAIMED LINE REPAIR", ["Repaired reclaimed line break.",
                                                        "Adjusted reclaimed valve, pressure restored."]),
}

# How the planner closes a request that needs no County crew. (log type, note)
NO_CREW_CLOSING = {
    "Backflow Device Issue": ("CLIENTNOTE", "Backflow devices belong to the property owner. Advised the customer "
                                            "to contact a licensed backflow tester or plumber."),
    "Drainage / Flooding": ("RESOLUTION", "Not a Utilities issue. Referred to Public Works Stormwater and closed. "
                                          "Classification corrected to Stormwater."),
}
