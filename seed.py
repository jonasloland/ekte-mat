"""Fyller databasen med syntetiske testdata: matretter, én admin og testkunder.

Kjør:  python seed.py      (sletter eksisterende data først)
"""
from datetime import date, datetime, timedelta

from app import create_app
from app.models.entities import Dish, GuestGroup, Order, OrderLine, OrderStatus, PaymentStatus, Question
from app.models.images import ImageGenerator
from app.models.repositories import create_repositories, reset_storage
from app.models.services import create_admin, register_customer

DISHES = [
    ("Fårikål", "Lam og kål i lag på lag, kokt med hel pepper. Servert med poteter.", 189, 20,
     ["konfirmasjon", "julebord"], [], ["glutenfri", "laktosefri"], "Lam fra Valdres"),
    ("Pinnekjøtt med kålrotstappe", "Saltet og tørket ribbe av lam, dampet på bjørkepinner.", 329, 15,
     ["julebord"], ["melk", "selleri"], ["glutenfri"], "Lam fra Voss"),
    ("Laksesnitter", "Røkt laks på grovt brød med eggerøre og dill.", 69, 30,
     ["bursdag", "konfirmasjon", "konferanse", "minnestund"], ["fisk", "gluten", "egg", "melk"], [], "Laks fra Hardanger"),
    ("Bløtkake", "Klassisk norsk bløtkake med jordbær og vaniljekrem. 12 stykker per kake.", 549, 1,
     ["bursdag", "konfirmasjon", "bryllup"], ["gluten", "egg", "melk"], ["vegetar"], None),
    ("Rekesmørbrød", "Håndpillede reker, majones, sitron og salat på loff.", 95, 20,
     ["bryllup", "sommerfest", "konferanse"], ["skalldyr", "gluten", "egg"], [], "Reker fra Skagerrak"),
    ("Linsegryte med koriander", "Varmende gryte med røde linser, kokosmelk og ris.", 139, 10,
     ["konferanse", "bursdag", "sommerfest"], ["selleri"], ["vegan", "glutenfri", "laktosefri", "halal"], None),
    ("Kransekake", "Tradisjonell kransekake for 30 personer.", 1290, 1,
     ["bryllup", "konfirmasjon"], ["notter", "egg"], ["vegetar", "glutenfri"], "Mandler fra Spania"),
    ("Spekematfat", "Spekeskinke, fenalår, spekepølse, rømme og flatbrød.", 165, 15,
     ["konfirmasjon", "bryllup", "sommerfest"], ["gluten", "melk", "sennep"], [], "Fra lokale gårder i Telemark"),
    ("Vegetar-wraps", "Hummus, grillede grønnsaker og feta i tortilla.", 79, 20,
     ["konferanse", "bursdag"], ["gluten", "melk", "sesam"], ["vegetar"], None),
    ("Ribbe med surkål", "Sprø ribbe, medisterkaker, surkål og saus.", 349, 15,
     ["julebord"], ["gluten", "melk", "selleri", "sennep"], [], "Gris fra Jæren"),
]


def seed():
    app = create_app()
    reset_storage(app.config)
    repos = create_repositories(app.config)
    store = app.extensions["image_store"]
    store.clear_all()

    admin = create_admin(repos, "admin@ektemat.no", "Ada Admin", "admin1234")
    kari = register_customer(repos, "kari@example.no", "Kari Nordmann", "kunde1234")
    ola = register_customer(repos, "ola@example.no", "Ola Bedrift AS", "kunde1234")

    dishes = []
    for i, (name, desc, price, min_order, cats, allergens, diets, origin) in enumerate(DISHES):
        prompt = f"{name}: {desc}"
        token = store.save_pending(ImageGenerator._placeholder(prompt), "svg")
        dish = Dish(None, name, desc, price, min_order, cats, allergens, diets,
                    published=(i != len(DISHES) - 1),  # siste rett er et upublisert utkast
                    image_path=store.commit(token), image_prompt=prompt, origin=origin)
        dishes.append(repos.dishes.add(dish))

    def line(dish, qty):
        return OrderLine(dish.id, dish.name, dish.price_nok, qty, list(dish.allergens))

    today = date.today()
    orders = [
        Order(None, kari.id, today + timedelta(days=21), 40, "Kirkeveien 12, 0368 Oslo",
              [line(dishes[0], 40), line(dishes[3], 4)],
              [GuestGroup("Barn", 10, "2 med nøtteallergi"), GuestGroup("Voksne", 30, "1 cøliaki")]),
        Order(None, ola.id, today + timedelta(days=7), 60, "Storgata 1, 0155 Oslo",
              [line(dishes[2], 60), line(dishes[5], 20), line(dishes[8], 40)],
              [GuestGroup("Veganere", 8, "Ingen animalske produkter")],
              status=OrderStatus.APPROVED, payment_status=PaymentStatus.INVOICED),
        Order(None, ola.id, today + timedelta(days=2), 25, "Storgata 1, 0155 Oslo",
              [line(dishes[2], 30), line(dishes[5], 10)], [],
              status=OrderStatus.IN_PREPARATION, payment_status=PaymentStatus.DEPOSIT),
        Order(None, kari.id, today - timedelta(days=30), 15, "Kirkeveien 12, 0368 Oslo",
              [line(dishes[1], 15)], [],
              status=OrderStatus.DELIVERED, payment_status=PaymentStatus.PAID,
              created_at=datetime.now() - timedelta(days=45)),
    ]
    for o in orders:
        repos.orders.add(o)

    q1 = repos.questions.add(Question(None, orders[0].id, kari.id,
                                      "Kan dere levere allerede kl. 11, og tar dere med servise?"))
    repos.questions.add(Question(None, orders[1].id, ola.id, "Kan vi bytte wraps til glutenfrie?"))
    repos.questions.answer(q1.id, "Hei! Levering kl. 11 går fint. Servise leies ut for 25 kr per kuvert.", admin.id)

    print(f"Seedet {len(dishes)} retter, 3 brukere og {len(orders)} bestillinger i {app.config['DATABASE_PATH']}")
    print("Admin:  admin@ektemat.no / admin1234")
    print("Kunder: kari@example.no / kunde1234, ola@example.no / kunde1234")


if __name__ == "__main__":
    seed()
