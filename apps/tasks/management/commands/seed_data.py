"""
Seed data management command.
Generates synthetic volunteers and tasks around Kyiv (50.45°N, 30.52°E)
for development and demo purposes.

Uses the Faker library for realistic-looking names/text.
"""
import random
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.tasks.models import Task
from apps.volunteers.models import VolunteerProfile

User = get_user_model()

# Kyiv bounding box (approx. 15 km radius)
KYIV_LAT = 50.4501
KYIV_LON = 30.5234
RADIUS_DEG = 0.135  # ~15 km in degrees


def rand_coord(center, radius):
    return center + random.uniform(-radius, radius)


SAMPLE_TASKS = [
    ("Food parcel delivery", "Deliver food parcels to families in need near Obolon district.", "вул. Оболонський просп., 1, Київ, Україна", 3),
    ("Medical supply transport", "Transport medical supplies from warehouse to clinic.", "вул. Борщагівська, 154, Київ, Україна", 3),
    ("Evacuation assistance", "Help elderly residents evacuate from affected area.", "вул. Хрещатик, 22, Київ, Україна", 3),
    ("Clothing distribution", "Sort and distribute donated winter clothing.", "вул. Велика Васильківська, 72, Київ, Україна", 2),
    ("Community kitchen help", "Assist in preparing and serving meals at the community kitchen.", "вул. Саксаганського, 59, Київ, Україна", 2),
    ("Document assistance", "Help residents fill out administrative documents.", "пл. Незалежності, 1, Київ, Україна", 1),
    ("Pet shelter support", "Care for animals at the temporary shelter.", "вул. Лаврська, 15, Київ, Україна", 1),
    ("Generator fuel delivery", "Deliver fuel canisters to residential generators.", "вул. Позняки, 2, Київ, Україна", 3),
    ("First aid post", "Staff a first aid post at the community centre.", "просп. Перемоги, 50, Київ, Україна", 2),
    ("Rubble clearance", "Assist in clearing debris from a damaged building.", "вул. Миколи Лєскова, 9, Київ, Україна", 2),
]


class Command(BaseCommand):
    help = "Seed the database with demo users and tasks."

    def handle(self, *args, **options):
        self.stdout.write("Seeding database...")

        # Create superuser / coordinator
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@example.com', 'admin123', role='coordinator')
            self.stdout.write(self.style.SUCCESS("  Created superuser: admin / admin123"))

        # Create coordinator
        if not User.objects.filter(username='coordinator1').exists():
            User.objects.create_user(
                'coordinator1', 'coord@example.com', 'coord123',
                role='coordinator', first_name='Maria', last_name='Kovalenko',
            )
            self.stdout.write(self.style.SUCCESS("  Created coordinator: coordinator1 / coord123"))

        # Create volunteers
        volunteer_names = [
            ('volunteer1', 'Olena', 'Petrenko'),
            ('volunteer2', 'Ivan', 'Shevchenko'),
            ('volunteer3', 'Sofia', 'Bondarenko'),
            ('volunteer4', 'Dmytro', 'Kravchenko'),
            ('volunteer5', 'Anna', 'Melnyk'),
        ]
        for username, first, last in volunteer_names:
            if not User.objects.filter(username=username).exists():
                user = User.objects.create_user(
                    username, f'{username}@example.com', 'vol123',
                    role='volunteer', first_name=first, last_name=last,
                )
                profile, _ = VolunteerProfile.objects.get_or_create(user=user)
                profile.last_latitude = rand_coord(KYIV_LAT, RADIUS_DEG)
                profile.last_longitude = rand_coord(KYIV_LON, RADIUS_DEG)
                profile.save()
                self.stdout.write(self.style.SUCCESS(f"  Created volunteer: {username} / vol123"))

        # Create tasks
        coordinator = User.objects.filter(role='coordinator').first()
        task_count = 0
        for title, description, address, priority in SAMPLE_TASKS:
            if not Task.objects.filter(title=title).exists():
                task = Task.objects.create(
                    title=title,
                    description=description,
                    address=address,
                    priority=priority,
                    status=Task.Status.OPEN,
                    created_by=coordinator,
                    # Use synthetic coords near Kyiv for demo (skip live geocoding in seed)
                    latitude=rand_coord(KYIV_LAT, RADIUS_DEG),
                    longitude=rand_coord(KYIV_LON, RADIUS_DEG),
                )
                task_count += 1

        self.stdout.write(self.style.SUCCESS(f"  Created {task_count} tasks."))
        self.stdout.write(self.style.SUCCESS("Database seeded successfully."))
        self.stdout.write("")
        self.stdout.write("Demo accounts:")
        self.stdout.write("  admin        / admin123  (superuser + coordinator)")
        self.stdout.write("  coordinator1 / coord123  (coordinator)")
        self.stdout.write("  volunteer1   / vol123    (volunteer)")
        self.stdout.write("  ...volunteer5/ vol123    (volunteer)")
