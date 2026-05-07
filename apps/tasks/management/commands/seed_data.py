"""
Наповнення БД тестовими даними.
"""
import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.accounts.models import Organization
from apps.tasks.models import Task
from apps.volunteers.models import Skill, VolunteerProfile

User = get_user_model()

HALLUNDA_LOCATIONS = [
    # (підказка назви, широта, довгота)
    ("Hallunda centrum",        59.2437, 17.8246),
    ("Norsborg",                59.2474, 17.8349),
    ("Alby",                    59.2520, 17.8455),
    ("Fittja",                  59.2522, 17.8609),
    ("Tumba centrum",           59.1983, 17.8353),
    ("Vårby gård",              59.2651, 17.8785),
    ("Slagsta",                 59.2621, 17.8543),
    ("Flemingsberg",            59.2178, 17.9426),
    ("Huddinge centrum",        59.2379, 17.9813),
    ("Skärholmen",              59.2772, 17.9076),
    ("Vårberg",                 59.2741, 17.9037),
    ("Kungens Kurva",           59.2630, 17.9254),
    ("Bredäng",                 59.3019, 17.9219),
    ("Sätra",                   59.2801, 17.9197),
    ("Liljeholmen",             59.3090, 18.0219),
]

TODAY = date.today()

SAMPLE_TASKS = [
    # (назва, опис, адреса, пріоритет, статус, потрібно_волонтерів, ключ_організації, архівовано, зміщення_початку_в_днях, тривалість_в_днях)
    (
        "Доставка продуктових наборів – Hallunda",
        "Доставка продуктових наборів літнім та малозабезпеченим мешканцям навколо центру Hallunda. Потрібен автомобіль.",
        "Hallunda torg 1, 145 68 Norsborg",
        3, Task.Status.OPEN, 2, "rk", False, 0, 1,
    ),
    (
        "Збір зимового одягу – Norsborg",
        "Сортування та роздача пожертвуваного зимового одягу в громадському центрі Norsborg.",
        "Norsborgs torg 3, 145 52 Norsborg",
        2, Task.Status.OPEN, 3, "rk", False, 2, 2,
    ),
    (
        "Транспортування медичних засобів – Tumba",
        "Транспортування медичних засобів зі складу в Tumba до місцевої клініки.",
        "Gymnasievägen 1, 147 40 Tumba",
        3, Task.Status.IN_PROGRESS, 1, "rk", False, -1, 3,
    ),
    (
        "Громадська кухня – Alby",
        "Допомога у приготуванні та роздачі гарячих страв на їдальні в Alby.",
        "Albybergsringen 30, 145 59 Norsborg",
        2, Task.Status.OPEN, 4, "fk", False, 1, 1,
    ),
    (
        "Репетиторство після школи – Fittja",
        "Допомога з домашніми завданнями дітям початкової школи у бібліотеці Fittja.",
        "Fittja torg 1, 145 72 Norsborg",
        1, Task.Status.OPEN, 2, "fk", False, 3, 7,
    ),
    (
        "Відвідування літніх людей вдома – Vårby",
        "Відвідування самотніх літніх мешканців Vårby для підтримки та допомоги з дрібними дорученнями.",
        "Vårby allé 50, 143 41 Vårby",
        2, Task.Status.OPEN, 1, "fk", False, 0, 14,
    ),
    (
        "Прибирання парку – Hallunda",
        "Збір сміття та догляд за парком Hallundaparken.",
        "Hallundaparken, 145 68 Norsborg",
        1, Task.Status.OPEN, 5, None, False, 5, 1,
    ),
    (
        "Підтримка біженців – Botkyrka",
        "Допомога новоприбулим біженцям з орієнтацією, оформленням документів та вивченням шведської мови.",
        "Botkyrka kommunhus, Munkhättevägen 45, 147 85 Tumba",
        3, Task.Status.OPEN, 2, None, False, 0, 30,
    ),
    (
        "Пункт першої допомоги – Skärholmen",
        "Чергування на пункті першої допомоги під час місцевих спортивних змагань у Skärholmen.",
        "Skärholmstorget 1, 127 48 Skärholmen",
        2, Task.Status.IN_PROGRESS, 2, "rk", False, -2, 2,
    ),
    (
        "Транспортування мешканців з інвалідністю – Flemingsberg",
        "Перевезення мешканців з обмеженими можливостями до лікарських прийомів у Flemingsberg.",
        "Hälsovägen 11, 141 57 Huddinge",
        3, Task.Status.OPEN, 1, None, False, 1, 5,
    ),
    (
        "Прибирання берегової смуги – Vårby",
        "Збір сміття вздовж берегової смуги озера Меларен поблизу Vårby gård.",
        "Vårby strandväg, 143 41 Vårby",
        1, Task.Status.OPEN, 6, "fk", False, 7, 1,
    ),
    (
        "Сортування на продовольчому банку – Huddinge",
        "Сортування та перепакування пожертвуваних продуктів на складі продовольчого банку Huddinge.",
        "Industrivägen 10, 141 48 Huddinge",
        2, Task.Status.OPEN, 3, None, False, 2, 1,
    ),
    (
        "Допомога в кризовому притулку – Bredäng",
        "Нічне чергування та підтримка у кризовому притулку Bredäng.",
        "Bredängs torg 10, 127 31 Skärholmen",
        3, Task.Status.COMPLETED, 2, "rk", True, -14, 2,
    ),
    (
        "Допомога з документами – Sätra",
        "Допомога мешканцям у заповненні адміністративних форм у громадському центрі Sätra.",
        "Sätragången 6, 127 38 Skärholmen",
        1, Task.Status.COMPLETED, 1, "fk", True, -10, 3,
    ),
    (
        "Тренування молодіжної команди – Tumba",
        "Проведення тренування для юніорів з футболу на спортивному майданчику Tumba IP.",
        "Tumba idrottsplats, Idrottsvägen 1, 147 40 Tumba",
        1, Task.Status.OPEN, 2, None, False, 4, 1,
    ),
    (
        "Термінова доставка засобів – Alby",
        "Термінова доставка засобів гігієни до тимчасового притулку в Alby.",
        "Alby torg, 145 59 Norsborg",
        3, Task.Status.OPEN, 1, "rk", False, 0, 1,
    ),
    (
        "Допомога літнім з садом – Hallunda",
        "Допомога літнім домовласникам у Hallunda з весняним упорядкуванням саду.",
        "Hallunda torg 5, 145 68 Norsborg",
        1, Task.Status.OPEN, 3, "fk", False, 6, 2,
    ),
    (
        "Інформування про донорство крові – Skärholmen",
        "Розповсюдження інформаційних листівок та реєстрація донорів у Skärholmen Centrum.",
        "Skärholmen Centrum, 127 48 Skärholmen",
        2, Task.Status.COMPLETED, 2, "rk", True, -7, 1,
    ),
]


class Command(BaseCommand):
    help = "Seed the database with Hallunda/Stockholm demo organisations, users, and tasks."

    def handle(self, *args, **options):
        self.stdout.write("Seeding database with Hallunda/Stockholm demo data...")

        # ── Навички ────────────────────────────────────────────────────────────
        SKILL_DEFS = [
            ('medical',   'Перша допомога'),
            ('medical',   'Серцево-легенева реанімація'),
            ('medical',   'Медсестринство'),
            ('medical',   'Психологічна підтримка'),
            ('transport', 'Водій автомобіля'),
            ('transport', 'Водій вантажівки'),
            ('transport', 'Велосипедист'),
            ('physical',  'Важка фізична праця'),
            ('physical',  'Будівництво'),
            ('practical', 'Приготування їжі'),
            ('practical', 'Прибирання'),
            ('practical', 'Догляд за дітьми'),
            ('practical', 'Догляд за літніми'),
            ('technical', 'ІТ-підтримка'),
            ('technical', 'Фотографія'),
            ('social',    'Організація заходів'),
            ('social',    'Робота з громадою'),
            ('social',    'Консультування'),
            ('language',  'Англійська'),
            ('language',  'Українська'),
            ('language',  'Шведська'),
            ('language',  'Арабська'),
            ('language',  'Сомалійська'),
        ]
        skill_objects = {}
        for category, name in SKILL_DEFS:
            obj, _ = Skill.objects.get_or_create(name=name, defaults={'category': category})
            skill_objects[name] = obj
        self.stdout.write(self.style.SUCCESS(f"  Ensured {len(skill_objects)} skills"))

        # Суперкористувач / адмін
        if not User.objects.filter(username="admin").exists():
            User.objects.create_superuser(
                "admin", "admin@example.com", "admin123", role="coordinator"
            )
            self.stdout.write(self.style.SUCCESS("  Created superuser: admin / admin123"))

        # Організації
        admin_user = User.objects.get(username="admin")

        rk_org, _ = Organization.objects.get_or_create(
            name="Röda Korset Botkyrka",
            defaults={"is_verified": True, "created_by": admin_user},
        )
        if not rk_org.is_verified:
            rk_org.is_verified = True
            rk_org.save()

        fk_org, _ = Organization.objects.get_or_create(
            name="Botkyrka Frivilligcenter",
            defaults={"is_verified": True, "created_by": admin_user},
        )
        if not fk_org.is_verified:
            fk_org.is_verified = True
            fk_org.save()

        # Неверифікована організація — існує, але не може публікувати завдання
        Organization.objects.get_or_create(
            name="Stockholms Hjälpkår",
            defaults={"is_verified": False, "created_by": admin_user},
        )

        self.stdout.write(self.style.SUCCESS("  Created organisations"))

        ORG_MAP = {"rk": rk_org, "fk": fk_org}

        # Координатори
        coordinators_data = [
            # (логін, пароль, ім'я, прізвище, організація, is_verified)
            ("coord_rk",   "coord123", "Erik",    "Lindqvist",  rk_org, True),
            ("coord_fk",   "coord123", "Ingrid",  "Bergström",  fk_org, True),
            ("coord_ind",  "coord123", "Lars",    "Nilsson",    None,   True),
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

        # Волонтери
        volunteers_data = [
            ("vol_anna",   "vol123", "Anna",    "Karlsson"),
            ("vol_ole",    "vol123", "Johan",   "Svensson"),
            ("vol_maja",   "vol123", "Maja",    "Andersson"),
            ("vol_tobias", "vol123", "Tobias",  "Eriksson"),
            ("vol_sara",   "vol123", "Sara",    "Johansson"),
            ("vol_henrik", "vol123", "Henrik",  "Larsson"),
        ]
        for username, password, first, last in volunteers_data:
            if not User.objects.filter(username=username).exists():
                u = User.objects.create_user(
                    username, f"{username}@example.com", password,
                    role="volunteer", first_name=first, last_name=last,
                )
                loc = random.choice(HALLUNDA_LOCATIONS)
                profile, _ = VolunteerProfile.objects.get_or_create(user=u)
                profile.last_latitude  = loc[1] + random.uniform(-0.02, 0.02)
                profile.last_longitude = loc[2] + random.uniform(-0.02, 0.02)
                all_skills = list(skill_objects.values())
                profile.skills.set(random.sample(all_skills, min(4, len(all_skills))))
                profile.save()
                self.stdout.write(self.style.SUCCESS(f"  Created volunteer: {username} / {password}"))

        # Завдання
        COORD_FOR_ORG = {
            "rk":  coord_objects["coord_rk"],
            "fk":  coord_objects["coord_fk"],
            None:  coord_objects["coord_ind"],
        }

        task_count = 0
        loc_cycle = list(HALLUNDA_LOCATIONS)
        random.shuffle(loc_cycle)

        for i, (title, desc, address, priority, status, vol_needed, org_key, archived, start_offset, duration) in enumerate(SAMPLE_TASKS):
            if Task.objects.filter(title=title).exists():
                continue

            loc = loc_cycle[i % len(loc_cycle)]
            creator = COORD_FOR_ORG[org_key]

            start = TODAY + timedelta(days=start_offset)
            end   = start + timedelta(days=duration)

            task = Task.objects.create(
                title=title,
                description=desc,
                address=address,
                priority=priority,
                status=status,
                volunteers_needed=vol_needed,
                created_by=creator,
                is_archived=archived,
                latitude=loc[1]  + random.uniform(-0.01, 0.01),
                longitude=loc[2] + random.uniform(-0.01, 0.01),
                start_date=start,
                end_date=end,
            )
            all_skills = list(skill_objects.values())
            n_skills = random.randint(0, 3)
            if n_skills:
                task.required_skills.set(random.sample(all_skills, n_skills))
            task_count += 1

        self.stdout.write(self.style.SUCCESS(f"  Created {task_count} tasks."))
        self.stdout.write(self.style.SUCCESS("Done. Demo accounts:"))
        self.stdout.write("")
        self.stdout.write("  admin      / admin123  — superuser")
        self.stdout.write("  coord_rk   / coord123  — coordinator, Röda Korset Botkyrka")
        self.stdout.write("  coord_fk   / coord123  — coordinator, Botkyrka Frivilligcenter")
        self.stdout.write("  coord_ind  / coord123  — independent coordinator (no org)")
        self.stdout.write("  vol_anna   / vol123    — volunteer")
        self.stdout.write("  vol_ole    / vol123    — volunteer")
        self.stdout.write("  vol_maja   / vol123    — volunteer")
        self.stdout.write("  vol_tobias / vol123    — volunteer")
        self.stdout.write("  vol_sara   / vol123    — volunteer")
        self.stdout.write("  vol_henrik / vol123    — volunteer")
