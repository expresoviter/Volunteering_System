"""
Seed data management command.
Generates demo organisations, coordinators, volunteers, and tasks
located in Akershus county, Norway.
"""
import random
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.accounts.models import Organization
from apps.tasks.models import Task
from apps.volunteers.models import Skill, VolunteerProfile

User = get_user_model()

# Akershus county approximate bounding box
AKERSHUS_LOCATIONS = [
    # (name hint, lat, lon)
    ("Sandvika, Bærum",        59.8853, 10.5281),
    ("Asker sentrum",          59.8336, 10.4392),
    ("Jessheim, Ullensaker",   60.1448, 11.1736),
    ("Lillestrøm",             59.9557, 11.0521),
    ("Ski, Nordre Follo",      59.7189, 10.8310),
    ("Drøbak, Frogn",          59.6617, 10.6152),
    ("Ås sentrum",             59.6601, 10.7877),
    ("Lørenskog sentrum",      59.9214, 10.9650),
    ("Nittedal",               60.0620, 10.8735),
    ("Eidsvoll sentrum",       60.3265, 11.2572),
    ("Nesodden",               59.7953, 10.6541),
    ("Nannestad",              60.2354, 11.1498),
    ("Enebakk",                59.7500, 11.0667),
    ("Rælingen",               59.9167, 11.0833),
    ("Vestby",                 59.5667, 10.7500),
]

SAMPLE_TASKS = [
    # (title, description, address, priority, status, volunteers_needed, org_key, archived)
    (
        "Food parcel delivery – Sandvika",
        "Deliver food parcels to elderly residents in the Sandvika area. Requires a car.",
        "Sandviksbodene 50, 1337 Sandvika",
        3, Task.Status.OPEN, 2, "rk", False,
    ),
    (
        "Winter clothing drive – Asker",
        "Sort and distribute donated winter clothing at the Asker community centre.",
        "Asker Torg 2, 1384 Asker",
        2, Task.Status.OPEN, 3, "rk", False,
    ),
    (
        "Medical supply transport – Jessheim",
        "Transport medical supplies from the Jessheim depot to the local health clinic.",
        "Rådhusplassen 1, 2050 Jessheim",
        3, Task.Status.IN_PROGRESS, 1, "rk", False,
    ),
    (
        "Community kitchen – Lillestrøm",
        "Assist in preparing and serving warm meals at the Lillestrøm soup kitchen.",
        "Storgata 9, 2001 Lillestrøm",
        2, Task.Status.OPEN, 4, "fk", False,
    ),
    (
        "After-school tutoring – Ski",
        "Provide homework help for primary school children at the Ski library.",
        "Idrettsveien 5, 1400 Ski",
        1, Task.Status.OPEN, 2, "fk", False,
    ),
    (
        "Elderly home visits – Drøbak",
        "Visit isolated elderly residents in Drøbak for companionship and light assistance.",
        "Storgata 32, 1440 Drøbak",
        2, Task.Status.OPEN, 1, "fk", False,
    ),
    (
        "Park clean-up – Ås",
        "Community litter pick and park maintenance in Ås town centre.",
        "Moerveien 10, 1430 Ås",
        1, Task.Status.OPEN, 5, None, False,
    ),
    (
        "Refugee welcome support – Lørenskog",
        "Help newly arrived refugees with orientation, paperwork, and language practice.",
        "Lørenskog sentrum, 1470 Lørenskog",
        3, Task.Status.OPEN, 2, None, False,
    ),
    (
        "First aid post – Nittedal",
        "Staff a first-aid post at the Nittedal local sports event.",
        "Rotnes, 1482 Nittedal",
        2, Task.Status.IN_PROGRESS, 2, "rk", False,
    ),
    (
        "Transport for disabled residents – Eidsvoll",
        "Drive residents with mobility challenges to medical appointments in Eidsvoll.",
        "Rådhusgata 1, 2080 Eidsvoll",
        3, Task.Status.OPEN, 1, None, False,
    ),
    (
        "Coastal clean-up – Nesodden",
        "Collect marine litter along the Nesodden shoreline.",
        "Nesoddtangen, 1450 Nesoddtangen",
        1, Task.Status.OPEN, 6, "fk", False,
    ),
    (
        "Food bank sorting – Nannestad",
        "Sort and repack donated food at the Nannestad food bank warehouse.",
        "Nannestad sentrum, 2030 Nannestad",
        2, Task.Status.OPEN, 3, None, False,
    ),
    (
        "Crisis shelter assistance – Enebakk",
        "Provide overnight support at the Enebakk emergency shelter.",
        "Enebakk sentrum, 1912 Enebakk",
        3, Task.Status.COMPLETED, 2, "rk", True,
    ),
    (
        "Document guidance – Rælingen",
        "Help residents complete administrative forms at the Rælingen municipal office.",
        "Smedsrudveien 1, 2005 Rælingen",
        1, Task.Status.COMPLETED, 1, "fk", True,
    ),
    (
        "Youth sports coaching – Vestby",
        "Coach a junior football session at Vestby sports ground.",
        "Vestby sentrum, 1540 Vestby",
        1, Task.Status.OPEN, 2, None, False,
    ),
    (
        "Emergency supply run – Lillestrøm",
        "Urgent delivery of hygiene kits to a temporary shelter in Lillestrøm.",
        "Jernbanegata 3, 2001 Lillestrøm",
        3, Task.Status.OPEN, 1, "rk", False,
    ),
    (
        "Garden help for elderly – Asker",
        "Assist elderly homeowners in Asker with spring garden tidying.",
        "Askerhagen 5, 1384 Asker",
        1, Task.Status.OPEN, 3, "fk", False,
    ),
    (
        "Blood donation awareness – Sandvika",
        "Distribute information leaflets and register donors at Sandvika Storsenter.",
        "Sandvika Storsenter, 1338 Sandvika",
        2, Task.Status.COMPLETED, 2, "rk", True,
    ),
]


class Command(BaseCommand):
    help = "Seed the database with Akershus-based demo organisations, users, and tasks."

    def handle(self, *args, **options):
        self.stdout.write("Seeding database with Akershus demo data...")

        # ── Skills ─────────────────────────────────────────────────────────────
        SKILL_DEFS = [
            ('medical',   'First Aid'),
            ('medical',   'CPR'),
            ('medical',   'Nursing'),
            ('medical',   'Mental Health Support'),
            ('transport', 'Car Driver'),
            ('transport', 'Truck Driver'),
            ('transport', 'Cyclist'),
            ('physical',  'Heavy Lifting'),
            ('physical',  'Construction'),
            ('practical', 'Cooking'),
            ('practical', 'Cleaning'),
            ('practical', 'Childcare'),
            ('practical', 'Elderly Care'),
            ('technical', 'IT Support'),
            ('technical', 'Photography'),
            ('social',    'Event Organisation'),
            ('social',    'Community Outreach'),
            ('social',    'Counselling'),
            ('language',  'English'),
            ('language',  'Ukrainian'),
            ('language',  'Norwegian'),
            ('language',  'Swedish'),
            ('language',  'German'),
        ]
        skill_objects = {}
        for category, name in SKILL_DEFS:
            obj, _ = Skill.objects.get_or_create(name=name, defaults={'category': category})
            skill_objects[name] = obj
        self.stdout.write(self.style.SUCCESS(f"  Ensured {len(skill_objects)} skills"))

        # ── Superuser / admin ──────────────────────────────────────────────────
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser(
                "admin", "admin@example.com", "admin123", role="coordinator"
            )
            self.stdout.write(self.style.SUCCESS("  Created superuser: admin / admin123"))

        # ── Organisations ──────────────────────────────────────────────────────
        admin_user = User.objects.get(username="admin")

        rk_org, _ = Organization.objects.get_or_create(
            name="Røde Kors Akershus",
            defaults={"is_verified": True, "created_by": admin_user},
        )
        if not rk_org.is_verified:
            rk_org.is_verified = True
            rk_org.save()

        fk_org, _ = Organization.objects.get_or_create(
            name="Frivilligsentralen Akershus",
            defaults={"is_verified": True, "created_by": admin_user},
        )
        if not fk_org.is_verified:
            fk_org.is_verified = True
            fk_org.save()

        # Unverified org — exists but cannot post tasks
        Organization.objects.get_or_create(
            name="Akershus Hjelpekorps",
            defaults={"is_verified": False, "created_by": admin_user},
        )

        self.stdout.write(self.style.SUCCESS("  Created organisations"))

        ORG_MAP = {"rk": rk_org, "fk": fk_org}

        # ── Coordinators ───────────────────────────────────────────────────────
        coordinators_data = [
            # (username, password, first, last, org, is_verified)
            ("coord_rk",   "coord123", "Erik",    "Hansen",   rk_org, True),
            ("coord_fk",   "coord123", "Ingrid",  "Berg",     fk_org, True),
            ("coord_ind",  "coord123", "Lars",    "Nilsson",  None,   True),
        ]
        coord_objects = {}
        for username, password, first, last, org, verified in coordinators_data:
            if not User.objects.filter(username=username).exists():
                u = User.objects.create_user(
                    username, f"{username}@example.com", password,
                    role="coordinator", first_name=first, last_name=last,
                    is_verified=verified, organization=org,
                )
                self.stdout.write(self.style.SUCCESS(f"  Created coordinator: {username} / {password}"))
            else:
                u = User.objects.get(username=username)
            coord_objects[username] = u

        # ── Volunteers ─────────────────────────────────────────────────────────
        volunteers_data = [
            ("vol_anna",   "vol123", "Anna",    "Larsen"),
            ("vol_ole",    "vol123", "Ole",     "Johansen"),
            ("vol_maja",   "vol123", "Maja",    "Andersen"),
            ("vol_tobias", "vol123", "Tobias",  "Eriksen"),
            ("vol_sara",   "vol123", "Sara",    "Dahl"),
            ("vol_henrik", "vol123", "Henrik",  "Lie"),
        ]
        for username, password, first, last in volunteers_data:
            if not User.objects.filter(username=username).exists():
                u = User.objects.create_user(
                    username, f"{username}@example.com", password,
                    role="volunteer", first_name=first, last_name=last,
                )
                loc = random.choice(AKERSHUS_LOCATIONS)
                profile, _ = VolunteerProfile.objects.get_or_create(user=u)
                profile.last_latitude  = loc[1] + random.uniform(-0.02, 0.02)
                profile.last_longitude = loc[2] + random.uniform(-0.02, 0.02)
                all_skills = list(skill_objects.values())
                profile.skills.set(random.sample(all_skills, min(4, len(all_skills))))
                profile.save()
                self.stdout.write(self.style.SUCCESS(f"  Created volunteer: {username} / {password}"))

        # ── Tasks ──────────────────────────────────────────────────────────────
        # Coordinator assignment: rk tasks → coord_rk, fk tasks → coord_fk, None → coord_ind
        COORD_FOR_ORG = {
            "rk":  coord_objects["coord_rk"],
            "fk":  coord_objects["coord_fk"],
            None:  coord_objects["coord_ind"],
        }

        task_count = 0
        loc_cycle = list(AKERSHUS_LOCATIONS)
        random.shuffle(loc_cycle)

        for i, (title, desc, address, priority, status, vol_needed, org_key, archived) in enumerate(SAMPLE_TASKS):
            if Task.objects.filter(title=title).exists():
                continue

            loc = loc_cycle[i % len(loc_cycle)]
            org = ORG_MAP.get(org_key)
            creator = COORD_FOR_ORG[org_key]

            task = Task.objects.create(
                title=title,
                description=desc,
                address=address,
                priority=priority,
                status=status,
                volunteers_needed=vol_needed,
                created_by=creator,
                is_archived=archived,
                latitude=loc[1] + random.uniform(-0.01, 0.01),
                longitude=loc[2] + random.uniform(-0.01, 0.01),
            )
            # Assign 0-3 random required skills per task
            all_skills = list(skill_objects.values())
            n_skills = random.randint(0, 3)
            if n_skills:
                task.required_skills.set(random.sample(all_skills, n_skills))
            task_count += 1

        self.stdout.write(self.style.SUCCESS(f"  Created {task_count} tasks."))
        self.stdout.write(self.style.SUCCESS("Done. Demo accounts:"))
        self.stdout.write("")
        self.stdout.write("  admin      / admin123  — superuser")
        self.stdout.write("  coord_rk   / coord123  — coordinator, Røde Kors Akershus")
        self.stdout.write("  coord_fk   / coord123  — coordinator, Frivilligsentralen Akershus")
        self.stdout.write("  coord_ind  / coord123  — independent coordinator (no org)")
        self.stdout.write("  vol_anna   / vol123    — volunteer")
        self.stdout.write("  vol_ole    / vol123    — volunteer")
        self.stdout.write("  vol_maja   / vol123    — volunteer")
        self.stdout.write("  vol_tobias / vol123    — volunteer")
        self.stdout.write("  vol_sara   / vol123    — volunteer")
        self.stdout.write("  vol_henrik / vol123    — volunteer")
