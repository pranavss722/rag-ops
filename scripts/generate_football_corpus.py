"""Generate an association football corpus from Wikipedia + hardcoded knowledge files."""

import json
import logging
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# American-football filter: skip articles whose *primary* topic is gridiron
# ---------------------------------------------------------------------------
GRIDIRON_KEYWORDS = re.compile(
    r"\b(American football|National Football League|NFL|touchdown|quarterback|"
    r"wide receiver|tight end|Super Bowl|gridiron)\b",
    re.IGNORECASE,
)


def _is_gridiron(text: str) -> bool:
    """Return True if text looks like it's primarily about American football."""
    first_2000 = text[:2000]
    hits = len(GRIDIRON_KEYWORDS.findall(first_2000))
    return hits >= 3


# ---------------------------------------------------------------------------
# Wikipedia fetcher
# ---------------------------------------------------------------------------
_WIKI_API = "https://en.wikipedia.org/w/api.php"


def _fetch_article(title: str) -> tuple[str, str | None]:
    """Fetch plain-text extract for a Wikipedia article. Returns (title, text|None)."""
    params = urllib.parse.urlencode({
        "action": "query",
        "titles": title,
        "prop": "extracts",
        "explaintext": "1",
        "format": "json",
        "redirects": "1",
    })
    url = f"{_WIKI_API}?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "FootballCorpusBot/1.0"})  # noqa: S310
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            data = json.loads(resp.read().decode())
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            text = page.get("extract")
            if text and len(text) > 200:
                if _is_gridiron(text):
                    return title, None
                return title, text
        return title, None
    except Exception:
        return title, None


# ---------------------------------------------------------------------------
# Article title lists  (association football ONLY)
# ---------------------------------------------------------------------------

CLUBS_ENGLAND = [
    "Manchester_United_F.C.", "Liverpool_F.C.", "Arsenal_F.C.",
    "Chelsea_F.C.", "Manchester_City_F.C.", "Tottenham_Hotspur_F.C.",
    "Everton_F.C.", "Newcastle_United_F.C.", "Aston_Villa_F.C.",
    "West_Ham_United_F.C.", "Leicester_City_F.C.", "Leeds_United_A.F.C.",
    "Wolverhampton_Wanderers_F.C.", "Crystal_Palace_F.C.",
    "Southampton_F.C.", "Nottingham_Forest_F.C.", "Fulham_F.C.",
    "Brentford_F.C.", "Brighton_&_Hove_Albion_F.C.", "Burnley_F.C.",
    "Sheffield_United_F.C.", "Luton_Town_F.C.", "Bournemouth_F.C.",
    "West_Bromwich_Albion_F.C.", "Sunderland_A.F.C.",
    "Middlesbrough_F.C.", "Stoke_City_F.C.", "Swansea_City_A.F.C.",
    "Cardiff_City_F.C.", "Queens_Park_Rangers_F.C.",
    "Derby_County_F.C.", "Blackburn_Rovers_F.C.", "Ipswich_Town_F.C.",
    "Coventry_City_F.C.", "Millwall_F.C.", "Charlton_Athletic_F.C.",
    "Preston_North_End_F.C.", "Blackpool_F.C.", "Hull_City_A.F.C.",
    "Bolton_Wanderers_F.C.", "Wigan_Athletic_F.C.",
    "Watford_F.C.", "Norwich_City_F.C.", "Reading_F.C.",
    "Birmingham_City_F.C.", "Sheffield_Wednesday_F.C.",
    "Bristol_City_F.C.", "Rotherham_United_F.C.", "Huddersfield_Town_A.F.C.",
]

CLUBS_SPAIN = [
    "FC_Barcelona", "Real_Madrid_CF", "Atletico_Madrid",
    "Sevilla_FC", "Real_Sociedad", "Real_Betis", "Valencia_CF",
    "Villarreal_CF", "Athletic_Club", "Osasuna", "Celta_Vigo",
    "Getafe_CF", "Girona_FC", "Rayo_Vallecano", "Cadiz_CF",
    "Deportivo_Alavés", "Granada_CF", "UD_Almería",
    "Real_Zaragoza", "Deportivo_de_La_Coruña", "Málaga_CF",
    "Sporting_de_Gijón", "RCD_Espanyol", "Levante_UD",
    "Real_Valladolid", "CD_Leganés", "SD_Eibar",
]

CLUBS_ITALY = [
    "Juventus_F.C.", "AC_Milan", "Inter_Milan", "AS_Roma",
    "SSC_Napoli", "Lazio", "Atalanta_B.C.", "Fiorentina",
    "Torino_FC", "Bologna_FC_1909", "Udinese_Calcio",
    "Sassuolo", "Hellas_Verona_F.C.", "Empoli_FC",
    "Genoa_CFC", "Sampdoria", "Cagliari_Calcio",
    "Venezia_FC", "Parma_Calcio_1913", "AC_Monza",
    "Frosinone_Calcio", "US_Lecce", "US_Salernitana_1919",
    "Spezia_Calcio", "AC_ChievoVerona", "Brescia_Calcio",
]

CLUBS_GERMANY = [
    "FC_Bayern_Munich", "Borussia_Dortmund", "RB_Leipzig",
    "Bayer_04_Leverkusen", "Borussia_Mönchengladbach",
    "Eintracht_Frankfurt", "VfL_Wolfsburg", "FC_Schalke_04",
    "Hamburger_SV", "Werder_Bremen", "VfB_Stuttgart",
    "TSG_1899_Hoffenheim", "SC_Freiburg", "Hertha_BSC",
    "FC_Augsburg", "VfL_Bochum", "FC_Union_Berlin",
    "1._FC_Köln", "1._FSV_Mainz_05", "Hannover_96",
    "1._FC_Nürnberg", "Fortuna_Düsseldorf", "MSV_Duisburg",
    "SpVgg_Greuther_Fürth", "FC_Heidenheim_1846",
]

CLUBS_FRANCE = [
    "Paris_Saint-Germain_F.C.", "Olympique_de_Marseille",
    "Olympique_Lyonnais", "AS_Monaco_FC", "Lille_OSC",
    "Stade_Rennais_F.C.", "RC_Lens", "OGC_Nice",
    "Montpellier_HSC", "Strasbourg", "Stade_de_Reims",
    "Nantes", "Toulouse_FC", "Clermont_Foot",
    "FC_Lorient", "Stade_Brestois_29", "Le_Havre_AC",
    "AJ_Auxerre", "SM_Caen", "Stade_Malherbe_Caen",
    "Girondins_de_Bordeaux", "AS_Saint-Étienne",
    "RC_Strasbourg_Alsace", "Valenciennes_FC",
]

CLUBS_NETHERLANDS = [
    "AFC_Ajax", "PSV_Eindhoven", "Feyenoord",
    "AZ_Alkmaar", "FC_Utrecht", "FC_Groningen",
    "SC_Heerenveen", "Vitesse", "FC_Twente",
    "Sparta_Rotterdam", "NAC_Breda", "FC_Emmen",
    "RKC_Waalwijk", "Excelsior_Rotterdam", "NEC_Nijmegen",
]

CLUBS_PORTUGAL = [
    "Benfica", "Sporting_CP", "FC_Porto",
    "SC_Braga", "Vitória_SC", "Rio_Ave_FC",
    "Boavista_FC", "CD_Santa_Clara", "GD_Chaves",
    "FC_Vizela", "FC_Famalicão", "Portimonense_SC",
]

CLUBS_REST_EUROPE = [
    "Celtic_F.C.", "Rangers_F.C.", "Heart_of_Midlothian_F.C.",
    "Hibernian_F.C.", "Aberdeen_F.C.", "Dundee_United_F.C.",
    "Club_Brugge_KV", "RSC_Anderlecht", "Standard_Liège",
    "Galatasaray_S.K.", "Fenerbahçe_S.K.", "Beşiktaş_JK",
    "Trabzonspor", "Başakşehir", "Shakhtar_Donetsk",
    "Dynamo_Kyiv", "CSKA_Moscow", "Spartak_Moscow",
    "Zenit_Saint_Petersburg", "Lokomotiv_Moscow",
    "Steaua_București", "Dinamo_București",
    "Legia_Warsaw", "Lech_Poznań", "Wisła_Kraków",
    "AC_Sparta_Prague", "SK_Slavia_Prague", "Bohemians_1905",
    "Red_Star_Belgrade", "FK_Partizan", "FK_Vojvodina",
    "Dinamo_Zagreb", "HNK_Rijeka", "Hajduk_Split",
    "Olympiacos_F.C.", "Panathinaikos_F.C.", "AEK_Athens_F.C.",
    "PAOK_FC", "Ferencváros_TC", "Újpest_FC",
    "Rosenborg_BK", "SK_Brann", "Malmö_FF",
    "IFK_Göteborg", "AIK_Fotboll", "Djurgårdens_IF",
    "FC_Copenhagen", "Brøndby_IF", "FC_Midtjylland",
    "HJK_Helsinki", "FK_Austria_Wien", "SK_Rapid_Wien",
    "FC_Red_Bull_Salzburg", "Young_Boys", "FC_Basel",
    "FC_Zürich", "GNK_Dinamo_Zagreb",
]

CLUBS_SOUTH_AMERICA = [
    "Boca_Juniors", "River_Plate", "Independiente",
    "Racing_Club_de_Avellaneda", "San_Lorenzo_de_Almagro",
    "Vélez_Sársfield", "Estudiantes_de_La_Plata",
    "Newell's_Old_Boys", "Rosario_Central",
    "Talleres_de_Córdoba", "Huracán",
    "Flamengo", "São_Paulo_FC", "Santos_FC", "Grêmio",
    "Sport_Club_Internacional", "Corinthians",
    "Palmeiras", "Cruzeiro", "Atlético_Mineiro",
    "Fluminense", "Vasco_da_Gama", "Botafogo",
    "Colo-Colo", "Universidad_de_Chile",
    "Universidad_Católica", "Cobreloa",
    "Club_Nacional_de_Football", "Club_Atlético_Peñarol",
    "Defensor_Sporting", "Danubio_FC",
    "Olimpia_(Paraguayan_football_club)", "Cerro_Porteño",
    "The_Strongest", "Club_Bolívar",
    "LDU_Quito", "Barcelona_SC",
    "Deportivo_Cali", "Atlético_Nacional",
    "Independiente_Santa_Fe", "Millonarios_FC",
    "Junior_FC", "Alianza_Lima", "Universitario_de_Deportes",
    "Sporting_Cristal", "Club_FBC_Melgar",
    "Club_Olimpia", "Club_Cerro_Porteño",
    "Club_Libertad", "Tacuary_FBC",
]

CLUBS_REST_WORLD = [
    "Al-Hilal_FC", "Al_Nassr_FC", "Al_Ittihad_Club",
    "Al_Ahli_Saudi_FC", "Al_Qadsiah_FC",
    "Al_Ahly_SC", "Zamalek_SC",
    "Esperance_Sportive_de_Tunis", "Wydad_AC",
    "Raja_Casablanca", "TP_Mazembe",
    "Mamelodi_Sundowns", "Kaizer_Chiefs",
    "Orlando_Pirates", "Urawa_Red_Diamonds",
    "Gamba_Osaka", "Kashima_Antlers",
    "Vissel_Kobe", "Kawasaki_Frontale",
    "Yokohama_F._Marinos", "Jeonbuk_Hyundai_Motors_FC",
    "Melbourne_City_FC", "Sydney_FC",
    "Melbourne_Victory_FC", "Western_Sydney_Wanderers_FC",
    "LA_Galaxy", "Seattle_Sounders_FC",
    "Portland_Timbers", "Atlanta_United_FC",
    "Inter_Miami_CF", "New_York_City_FC",
    "New_England_Revolution", "Columbus_Crew",
    "Philadelphia_Union", "Chicago_Fire_FC",
    "DC_United", "Toronto_FC",
    "Vancouver_Whitecaps_FC", "Club_de_Foot_Montréal",
]

PLAYERS_LEGENDS = [
    "Pelé", "Diego_Maradona", "Johan_Cruyff", "Franz_Beckenbauer",
    "Ronaldo_(Brazilian_footballer)", "Ronaldinho", "Zinedine_Zidane",
    "Roberto_Carlos", "Cafu", "Thierry_Henry", "Patrick_Vieira",
    "Paolo_Maldini", "Franco_Baresi", "Alessandro_Del_Piero",
    "Gabriel_Batistuta", "Rivaldo", "Romário", "Hristo_Stoichkov",
    "George_Best", "Bobby_Charlton", "Denis_Law", "Gordon_Banks",
    "Gerd_Müller", "Karl-Heinz_Rummenigge", "Lothar_Matthäus",
    "Michel_Platini", "Marco_van_Basten", "Ruud_Gullit", "Frank_Rijkaard",
    "Eusébio", "Lev_Yashin", "Garrincha", "Didi_(footballer)",
    "Bobby_Moore", "Geoff_Hurst", "Jimmy_Greaves", "Roger_Byrne",
    "Duncan_Edwards", "Tommy_Taylor", "Eddie_Colman",
    "Alfredo_Di_Stéfano", "Ferenc_Puskás", "Raymond_Kopa",
    "Just_Fontaine", "Sándor_Kocsis", "Nándor_Hidegkuti",
    "Giuseppe_Meazza", "Silvio_Piola", "Valentino_Mazzola",
    "Giacinto_Facchetti", "Dino_Zoff", "Gianni_Rivera",
    "Sandro_Mazzola", "Luigi_Riva", "Roberto_Baggio",
    "Franco_Causio", "Romeo_Benetti", "Claudio_Gentile",
    "Gaetano_Scirea", "Marco_Tardelli", "Paolo_Rossi",
    "Karl_Rappan", "Helmut_Rahn", "Sepp_Maier",
    "Berti_Vogts", "Jupp_Heynckes", "Paul_Breitner",
    "Bernd_Schuster", "Andreas_Brehme", "Rudi_Völler",
    "Jürgen_Klinsmann", "Oliver_Kahn", "Mehmet_Scholl",
    "Christian_Ziege", "Stefan_Effenberg", "Michael_Ballack",
    "Jens_Lehmann", "Per_Mertesacker", "Miroslav_Klose",
    "Lukas_Podolski", "Sami_Khedira", "Mario_Götze",
]

PLAYERS_GOLDEN_GEN = [
    "Lionel_Messi", "Cristiano_Ronaldo", "Xavi",
    "Andres_Iniesta", "Sergio_Ramos", "Carles_Puyol",
    "Gerard_Pique", "Victor_Valdes", "Neymar",
    "Luis_Suarez", "Zlatan_Ibrahimović", "Didier_Drogba",
    "Frank_Lampard", "John_Terry", "Petr_Cech",
    "Steven_Gerrard", "Wayne_Rooney", "Michael_Owen",
    "Rio_Ferdinand", "Sol_Campbell", "Ashley_Cole",
    "David_Beckham", "Peter_Schmeichel", "Roy_Keane",
    "Paul_Scholes", "Ryan_Giggs", "Gary_Neville",
    "Ruud_van_Nistelrooy", "Ole_Gunnar_Solskjær",
    "Andy_Cole", "Dwight_Yorke", "Teddy_Sheringham",
    "Robbie_Fowler", "Emile_Heskey",
    "Dion_Dublin", "Ian_Wright", "Tony_Adams",
    "Martin_Keown", "Lee_Dixon", "Nigel_Winterburn",
    "Marc_Overmars", "Emmanuel_Petit", "Sylvain_Wiltord",
    "Freddie_Ljungberg", "Robert_Pirès", "Dennis_Bergkamp",
    "Nicolas_Anelka", "David_Seaman",
    "Luka_Modrić", "Toni_Kroos", "Karim_Benzema",
    "Gareth_Bale", "Iker_Casillas", "Xabi_Alonso",
    "Marcelo_(footballer)", "Sergio_Busquets", "Dani_Alves",
    "Gianluigi_Buffon", "Andrea_Pirlo", "Francesco_Totti",
    "Alessandro_Nesta", "Filippo_Inzaghi", "Clarence_Seedorf",
    "Kaká", "Samuel_Eto'o", "Yaya_Touré", "Michael_Essien",
    "Arjen_Robben", "Franck_Ribéry", "Thomas_Müller",
    "Bastian_Schweinsteiger", "Philipp_Lahm", "Manuel_Neuer",
    "Mesut_Özil", "Robin_van_Persie",
    "Wesley_Sneijder", "Dirk_Kuyt", "Rafael_van_der_Vaart",
    "Mark_van_Bommel", "Nigel_de_Jong", "Gregory_van_der_Wiel",
    "Maarten_Stekelenburg", "John_Heitinga", "Joris_Mathijsen",
    "Sergio_Agüero", "Carlos_Tevez", "Gonzalo_Higuaín",
    "Javier_Mascherano", "Pablo_Zabaleta", "Marcos_Rojo",
    "Ezequiel_Garay", "Ángel_Di_María", "Éver_Banega",
    "Maxi_Rodríguez", "Rodrigo_Palacio", "Erik_Lamela",
    "Hernán_Crespo", "Juan_Román_Riquelme", "Pablo_Aimar",
    "Javier_Saviola", "Marcelo_Gallardo", "Ariel_Ortega",
    "Claudio_López", "Martín_Palermo", "Guillermo_Barros_Schelotto",
    "Ivan_Rakitić", "Mario_Mandžukić", "Darijo_Srna",
    "Stipe_Pletikosa", "Robert_Kovač", "Niko_Kovač",
    "Dario_Šimić", "Igor_Tudor", "Slaven_Bilić", "Dado_Pršo",
]

PLAYERS_CURRENT = [
    "Kylian_Mbappé", "Erling_Haaland", "Vinicius_Junior",
    "Rodri", "Jude_Bellingham", "Phil_Foden", "Bukayo_Saka",
    "Mohamed_Salah", "Sadio_Mané", "Roberto_Firmino",
    "Virgil_van_Dijk", "Alisson_Becker", "Kevin_De_Bruyne",
    "Bernardo_Silva", "Riyad_Mahrez", "Harry_Kane",
    "Son_Heung-min", "Marcus_Rashford", "Bruno_Fernandes",
    "Casemiro", "Federico_Valverde", "Eduardo_Camavinga",
    "Aurélien_Tchouaméni", "Pedri", "Gavi",
    "Robert_Lewandowski", "Jamal_Musiala", "Leroy_Sané",
    "Serge_Gnabry", "Kingsley_Coman", "Thomas_Müller",
    "Leon_Goretzka", "Joshua_Kimmich", "Dayot_Upamecano",
    "Lucas_Hernández", "Benjamin_Pavard", "Alphonso_Davies",
    "Noussair_Mazraoui", "Ryan_Gravenberch", "Cole_Palmer",
    "Lamine_Yamal", "Dani_Olmo", "Mikel_Oyarzabal",
    "Alejandro_Balde", "Pau_Cubarsí", "Fermín_López",
    "Raphinha", "Jules_Koundé", "Gianluigi_Donnarumma",
    "Theo_Hernández", "Mike_Maignan", "Fikayo_Tomori",
    "Malick_Thiaw", "Loftus-Cheek", "Christian_Pulisic",
    "Samuel_Chukwueze", "Lautaro_Martínez", "Marcus_Thuram",
    "Nicolò_Barella", "Hakan_Çalhanoğlu", "Federico_Dimarco",
    "Alessandro_Bastoni", "Piotr_Zieliński", "Romelu_Lukaku",
    "Declan_Rice", "Martin_Ødegaard", "Gabriel_Jesus",
    "William_Saliba", "Gabriel_Magalhães", "David_Raya",
    "Kai_Havertz", "Leandro_Trossard", "Oleksandr_Zinchenko",
    "Thomas_Partey", "Moises_Caicedo", "Enzo_Fernández",
    "Reece_James", "Noni_Madueke",
    "Conor_Gallagher", "Nicolas_Jackson", "Christopher_Nkunku",
    "Dejan_Kulusevski", "Richarlison", "Cristian_Romero",
    "Pedro_Porro", "James_Maddison", "Guglielmo_Vicario",
    "Josko_Gvardiol", "Stefan_Ortega", "Jack_Grealish",
    "John_Stones", "Kyle_Walker", "Rúben_Dias",
    "Matheus_Nunes", "İlkay_Gündoğan", "Darwin_Núñez",
    "Cody_Gakpo", "Harvey_Elliott", "Alexis_Mac_Allister",
    "Wataru_Endo", "Trent_Alexander-Arnold", "Joe_Gomez",
    "Joel_Matip", "Andy_Robertson", "Konstantinos_Tsimikas",
    "Curtis_Jones", "Luis_Díaz", "Diogo_Jota",
    "Dominik_Szoboszlai", "Federico_Chiesa",
    "Dusan_Vlahovic", "Adrien_Rabiot", "Federico_Gatti",
    "Gleison_Bremer", "Danilo_(footballer)", "Alex_Sandro",
    "Wojciech_Szczęsny", "Weston_McKennie", "Fabio_Miretti",
    "Kenan_Yıldız", "Andrea_Cambiaso", "Timothy_Weah",
]

MANAGERS = [
    "Alex_Ferguson", "Pep_Guardiola", "José_Mourinho",
    "Jürgen_Klopp", "Carlo_Ancelotti", "Arrigo_Sacchi",
    "Rinus_Michels", "Helenio_Herrera",
    "Telê_Santana", "Marcelo_Bielsa", "Osvaldo_Zubeldía",
    "Béla_Guttmann", "Herbert_Chapman", "Bill_Shankly",
    "Bob_Paisley", "Brian_Clough", "Matt_Busby",
    "Aimé_Jacquet", "Didier_Deschamps", "Vicente_del_Bosque",
    "Luis_Enrique", "Diego_Simeone", "Antonio_Conte",
    "Mauricio_Pochettino", "Thomas_Tuchel", "Zinedine_Zidane",
    "Erik_ten_Hag", "Xabi_Alonso", "Mikel_Arteta",
    "Roberto_De_Zerbi", "Eddie_Howe", "Graham_Potter",
    "Brendan_Rodgers", "David_Moyes", "Sam_Allardyce",
    "Tony_Pulis", "Steve_Bruce", "Neil_Warnock",
    "Gareth_Southgate",
    "Sven-Göran_Eriksson", "Steve_McClaren",
    "Terry_Venables", "Kevin_Keegan", "Glenn_Hoddle",
    "Fabio_Capello", "Roy_Hodgson", "Bobby_Robson",
    "Don_Revie", "Alf_Ramsey", "Walter_Winterbottom",
    "Arsène_Wenger",
    "Claudio_Ranieri", "Walter_Mazzarri", "Maurizio_Sarri",
    "Roberto_Mancini", "Luciano_Spalletti", "Simone_Inzaghi",
    "Stefano_Pioli", "Massimiliano_Allegri",
    "Unai_Emery", "Ernesto_Valverde",
    "Louis_van_Gaal",
    "Guus_Hiddink", "Dick_Advocaat",
    "Julian_Nagelsmann", "Ralf_Rangnick",
    "Ottmar_Hitzfeld", "Giovanni_Trapattoni",
]

NATIONAL_TEAMS = [
    "Brazil_national_football_team",
    "Argentina_national_football_team",
    "Germany_national_football_team",
    "France_national_football_team",
    "Spain_national_football_team",
    "Italy_national_football_team",
    "England_national_football_team",
    "Netherlands_national_football_team",
    "Portugal_national_football_team",
    "Belgium_national_football_team",
    "Uruguay_national_football_team",
    "Croatia_national_football_team",
    "Denmark_national_football_team",
    "Sweden_national_football_team",
    "Norway_national_football_team",
    "Mexico_national_football_team",
    "Japan_national_football_team",
    "South_Korea_national_football_team",
    "Nigeria_national_football_team",
    "Senegal_national_football_team",
    "Cameroon_national_football_team",
    "Ghana_national_football_team",
    "Morocco_national_football_team",
    "Egypt_national_football_team",
    "Australia_national_football_team",
    "Colombia_national_football_team",
    "Chile_national_football_team",
    "Peru_national_football_team",
    "Poland_national_football_team",
    "Czech_Republic_national_football_team",
    "Switzerland_national_football_team",
    "Austria_national_football_team",
    "Turkey_national_football_team",
    "Greece_national_football_team",
    "Ukraine_national_football_team",
    "Serbia_national_football_team",
    "Hungary_national_football_team",
    "Scotland_national_football_team",
    "Wales_national_football_team",
    "Republic_of_Ireland_national_football_team",
    "Saudi_Arabia_national_football_team",
    "Iran_national_football_team",
    "Algeria_national_football_team",
    "Tunisia_national_football_team",
    "Ecuador_national_football_team",
    "Paraguay_national_football_team",
    "Bolivia_national_football_team",
    "Venezuela_national_football_team",
    "Costa_Rica_national_football_team",
    "Panama_national_football_team",
    "Jamaica_national_football_team",
    "Trinidad_and_Tobago_national_football_team",
    "United_States_men's_national_soccer_team",
    "Canada_men's_national_soccer_team",
    "New_Zealand_national_football_team",
    "South_Africa_national_football_team",
    "Ivory_Coast_national_football_team",
    "Iceland_national_football_team",
    "Romania_national_football_team",
    "Bulgaria_national_football_team",
    "Slovakia_national_football_team",
    "Slovenia_national_football_team",
    "Bosnia_and_Herzegovina_national_football_team",
    "Albania_national_football_team",
    "Georgia_national_football_team",
    "Iraq_national_football_team",
    "Qatar_national_football_team",
    "India_national_football_team",
    "China_national_football_team",
]

TOURNAMENTS = [
    "FIFA_World_Cup", "UEFA_Champions_League",
    "Premier_League", "La_Liga", "Serie_A",
    "Bundesliga", "Ligue_1", "UEFA_Europa_League",
    "UEFA_Conference_League", "UEFA_Nations_League",
    "UEFA_European_Championship", "Copa_América",
    "Copa_Libertadores", "Copa_Sudamericana",
    "FIFA_Club_World_Cup", "Intercontinental_Cup_(football)",
    "FA_Cup", "EFL_Championship", "EFL_League_One",
    "EFL_League_Two", "Carabao_Cup", "Community_Shield",
    "UEFA_Super_Cup", "Supercopa_de_España",
    "Copa_del_Rey", "Supercoppa_Italiana", "Coppa_Italia",
    "DFB-Pokal", "DFL-Supercup", "Coupe_de_France",
    "Trophée_des_Champions", "Scottish_Premiership",
    "Eredivisie", "KNVB_Cup", "Belgian_First_Division_A",
    "Primeira_Liga", "Taça_de_Portugal",
    "Super_Lig", "CAF_Champions_League",
    "Africa_Cup_of_Nations", "CONCACAF_Champions_Cup",
    "CONCACAF_Gold_Cup", "AFC_Champions_League",
    "AFC_Asian_Cup", "FIFA_Confederations_Cup",
    "Olympic_football",
    "FIFA_U-20_World_Cup", "FIFA_U-17_World_Cup",
    "UEFA_European_Under-21_Championship",
    "UEFA_Youth_League",
]

WORLD_CUP_EDITIONS = [
    "2022_FIFA_World_Cup", "2018_FIFA_World_Cup",
    "2014_FIFA_World_Cup", "2010_FIFA_World_Cup",
    "2006_FIFA_World_Cup", "2002_FIFA_World_Cup",
    "1998_FIFA_World_Cup", "1994_FIFA_World_Cup",
    "1990_FIFA_World_Cup", "1986_FIFA_World_Cup",
    "1982_FIFA_World_Cup", "1978_FIFA_World_Cup",
    "1974_FIFA_World_Cup", "1970_FIFA_World_Cup",
    "1966_FIFA_World_Cup", "1962_FIFA_World_Cup",
    "1958_FIFA_World_Cup", "1954_FIFA_World_Cup",
    "1950_FIFA_World_Cup", "1938_FIFA_World_Cup",
    "1934_FIFA_World_Cup", "1930_FIFA_World_Cup",
]

HISTORY_AND_CULTURE = [
    "Association_football", "History_of_association_football",
    "Laws_of_the_game_(association_football)",
    "Football_pitch", "Football_(ball)", "Football_boot",
    "Goalkeeper_(association_football)",
    "Defender_(association_football)",
    "Midfielder", "Forward_(association_football)",
    "Offside_(association_football)",
    "VAR_(association_football)",
    "Goal-line_technology",
    "Penalty_kick_(association_football)",
    "Free_kick_(association_football)",
    "Transfer_fee", "Bosman_ruling",
    "Football_hooliganism",
    "El_Clásico", "Der_Klassiker",
    "Superclásico",
    "FIFA", "UEFA", "CONMEBOL",
    "Ballon_d'Or", "FIFA_Best_Men's_Player_Award",
    "Golden_Boot_(award)",
    "Expected_goals",
    "Hillsborough_disaster", "Heysel_stadium_disaster",
    "Munich_air_disaster",
    "Hand_of_God_(1986_FIFA_World_Cup)",
    "Tiki-taka", "Gegenpressing", "Total_Football",
    "Catenaccio",
]

MEDIA_PERSONALITIES = [
    "Gary_Lineker", "Alan_Shearer",
    "Jamie_Carragher", "Fabrizio_Romano",
    "Martin_Tyler", "Peter_Drury", "John_Motson",
    "Guillem_Balagué",
]


def _all_titles() -> list[str]:
    """Collect and deduplicate all Wikipedia article titles."""
    combined = (
        CLUBS_ENGLAND + CLUBS_SPAIN + CLUBS_ITALY + CLUBS_GERMANY
        + CLUBS_FRANCE + CLUBS_NETHERLANDS + CLUBS_PORTUGAL
        + CLUBS_REST_EUROPE + CLUBS_SOUTH_AMERICA + CLUBS_REST_WORLD
        + PLAYERS_LEGENDS + PLAYERS_GOLDEN_GEN + PLAYERS_CURRENT
        + MANAGERS + NATIONAL_TEAMS + TOURNAMENTS
        + WORLD_CUP_EDITIONS + HISTORY_AND_CULTURE + MEDIA_PERSONALITIES
    )
    seen: set[str] = set()
    unique: list[str] = []
    for t in combined:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


# ---------------------------------------------------------------------------
# Hardcoded content files
# ---------------------------------------------------------------------------

FOOTBALL_WISDOM = r"""# Football Wisdom: Quotes from the Beautiful Game

## Sir Alex Ferguson

"In my time at Manchester United, the weights of expectation were never an issue. Expectation is what you expect of yourself."
"The work of a team should always embrace a great player but the great player must always work."
"I tell players: If you play with fire you get burned."
"Concentration is one of the most difficult things for a footballer to maintain. It's easy for them to switch off, but the best players never do."
"Sometimes you have a noisy one in the dressing room, and I'm not sure it works. It is better if they simply follow instructions."
"Attack wins you games, defence wins you titles."
"I used to have a saying that when a player is at his peak, he feels as though he can climb Everest in his slippers."
"My greatest challenge was knocking Liverpool right off their f***ing perch. And you can print that."
"Failure is not fatal, but failure to change might be."
"For a player, once you've experienced the buzz of scoring a goal, you don't forget it."
"You can't ever lose it. Winning is in my nature. I've tried to develop that in everything I've done."
"I think that what really matters is discipline and hard work."
"After 1998, we were on fire. Every year after that we seemed to peak."
"If he could pass the ball, his name would be Pelé."
"I've never played for a draw in my life."
"Sometimes in football you have to score goals."
"The best thing about being a manager is winning. The worst is losing."
"I didn't enjoy the last two years because my assistant went to another club."
"Never give in, never give in, never, never, never."
"Experience is not what happens to a man, it is what a man does with what happens to him."
"When you are managing Manchester United, you cannot afford to stand still."
"Football is a game of opinions, and you have to state yours and move on."
"I breathe football. I breathe Manchester United."
"No one likes to be criticized. Few people get better with criticism; most respond to encouragement instead."
"If we can play like that every week we'll get some level of consistency."

## Pep Guardiola

"I learned from Johan Cruyff that the priority is to attack."
"When you attack, you need to have the ball. And when you defend, you must get it back."
"In football everything is complicated by the presence of the opposite team."
"Take the ball, pass the ball."
"I want my teams to play in the opponent's half. I want to recover the ball as high as possible."
"Don't write about what I say. Watch what my teams do."
"The day I am not able to transmit to my players what I believe in, I will leave."
"Everyone says I am a defensive coach, but I just want to control the game."
"We cannot control the result, but we can control our performance."
"In football, the result is an impostor. You can do things really well but not win."
"Perfection doesn't exist in football. But it is the aim."
"I want my winger to stay wide. I want my midfielder to think."
"Football is not about individuals. It's about the collective."
"The secret is not the system. The secret is how the players interpret the system."
"I don't coach positions, I coach movements."
"The worst enemy of the coach is the result. The result can make you complacent."
"I try to make my teams play in a certain way. If you don't like it, I'm sorry."
"Every time I see a football pitch I feel small. The game is bigger than any of us."
"We play the way we play because I believe it gives us the best chance to win."
"Football is simple — the hardest thing is to play simple football."
"When I don't have the ball, I cannot enjoy myself. So I want the ball."
"My teams have to play with joy. I want to see players who enjoy what they do."
"Pressing is the best playmaker. When you win the ball high, you are closer to the goal."
"Without the ball you are nothing."
"The positional game is the most important concept in modern football."

## José Mourinho

"Please don't call me arrogant, but I'm European champion and I think I'm a special one."
"I am not the one to explain what is going on. I know what happens in football."
"I have nothing to say. If I speak, I am in big trouble."
"The title race is between two horses and a little horse that needs milk and needs to learn how to jump."
"I am José Mourinho and I don't change. I arrive with all my qualities and all my defects."
"If I wanted to have an easy job, I would have stayed at Porto. Beautiful blue chair, the UEFA Champions League trophy."
"Look, I'm a coach. I'm not Harry Potter."
"Football is a game about feelings and speed. It is not about a computer."
"Everyone knows I have no contract, but I want to stay."
"I think the best team drew and the worst team won."
"I prefer not to speak. If I speak, I'm in big trouble."
"Zero trophies is what some managers win. I am never there."
"Pressure? What pressure? Pressure is the millions of parents who can't afford to feed their children."
"I'm not a defender of old or new football managers. I believe in good ones and bad ones."
"If I have a problem, I deal with it myself."
"I don't want to win the Europa League. It would be a big disappointment for me."
"In five years I have never been behind at half-time."
"Young players are like melons. Only when you open and taste the melon are you 100% sure that the melon is good."
"I studied Italian five hours a day for many months to be ready."
"The Porto/Chelsea/Inter/Real motto is the same: we win together."
"I'm not going to change. I will always be direct, sometimes controversial."
"Results speak louder than words."
"Mind games? Let them play mind games. I play football games."
"I don't regret anything. In my career, I always gave everything."
"Football heritage? I don't want to leave a heritage. I want to leave trophies."

## Jürgen Klopp

"I am the normal one."
"We have to change from doubters to believers."
"If you don't believe, why are you even here?"
"I don't believe in individual talent. I believe in team spirit."
"Heavy metal football — that's what I want."
"Gegenpressing is the best playmaker in the world."
"The best moment? I haven't had it yet."
"We lost against the best team in the world, and that's Manchester City. The second best is in this room."
"Do I look happy? I am happy! We won a football match!"
"I never succeed by sitting in my chair and thinking about things."
"Even Disneyland is not as nice as Anfield on a European night."
"Boom! That's what football is about!"
"I love this game. I love these players. I love this club."
"Football without fans is nothing."
"We will try and we will try again. That's what football is."
"It's not about money. It's about running harder, fighting more and being together."
"I told my players at half-time: 'Go out there and give them hell.'"
"I am a totally normal guy from the Black Forest."
"I wasn't born here, I wasn't raised here, but I feel at home."
"It's the intensity and the passion — that's what supporters want to see."

## Johan Cruyff

"Playing football is very simple, but playing simple football is the hardest thing there is."
"If I wanted you to understand, I would have explained it better."
"Quality without results is pointless. Results without quality is boring."
"Why couldn't you beat a richer club? I've never seen a bag of money score a goal."
"Speed is often confused with insight. When I start running earlier than the others, I appear faster."
"Every disadvantage has its advantage."
"Before I make a mistake, I don't make that mistake."
"In my teams, the weights are always wrong. We have too many light ones."
"Football is a game of errors. Whoever makes the fewest errors wins."
"There is only one ball, so you need to have it."
"I'm not religious. In Spain all 22 players cross themselves before a match. If it works, every game should end in a draw."
"Technique is not being able to juggle a ball 1000 times. Anyone can do that by practising. Then you can work in the circus. Technique is passing the ball with one touch, with the right speed, at the right foot of your teammate."
"Choose the best player for every position, and you'll not end up with the best team, but with 11 individuals."
"To play well you need good players, but you can still play badly with good players."
"If you have the ball you must make the field as big as possible, and if you don't have the ball you must make it as small as possible."
"I always think: is there a way to do it better?"
"The game has laws, and you must learn them. But you must also learn when to ignore them."
"Without the ball, you can't win."
"Football should be played beautifully. It is an art."
"In football, the worst things are usually the best lessons."
"Italians can't beat you, but you can lose against them."
"Players that aren't true leaders but try to be, always come across as false."
"We had the ball at Barcelona for 65% of the game. Why? Because it is very difficult to score when you don't have the ball."
"My father always said: if you score three goals and concede two, you always win."
"There are very few players who know what to do when they don't have the ball. So make sure you have it."
"When you play a match, it is statistically proven that players actually have the ball three minutes on average. So, the most important thing is: what do you do during the 87 minutes when you do not have the ball?"
"At Barcelona we made the pitch as big as possible when we had the ball, and as small as possible when we didn't."
"Good football is about being quick in your head, not quick with your legs."
"You play football with your head, and your legs are there to help you."
"Goalkeepers should play football too. At Barcelona, I wanted the goalkeeper to be the eleventh outfield player."
"The Dutch invented Total Football but never won a World Cup. Sometimes perfection is not enough."
"Better to fail with honour than succeed by fraud."
"I don't make predictions. I never have, and I never will."
"Football is a game you play with your brain."
"If you can't win, make sure you don't lose."

## Bill Shankly

"Some people believe football is a matter of life and death. I am very disappointed with that attitude. I can assure you it is much, much more important than that."
"If Everton were playing at the bottom of the garden, I'd close the curtains."
"Football is a simple game based on the giving and taking of passes, of ## controlling the ball and of making yourself available to receive a pass."
"The socialism I believe in is everyone working for each other, everyone having a share of the rewards."
"Above all, I would like to be remembered as a man who was selfless, who strove and worried so that others could share the rewards."
"If you are first you are first. If you are second, you are nothing."
"This is a football club and I want everyone to be happy."
"I want to build a team that's invincible, so that they have to send a team from Mars to beat us."
"The trouble with referees is that they know the rules, but they don't know the game."
"At a football club, there's a holy trinity: the players, the manager, and the supporters."
"Chairman Mao has never seen such a show of red strength."
"We murdered them 0-0."
"A lot of football success is in the mind."
"Tom Finney would have been great in any team, in any match and in any age."
"I don't drop players, I make changes."
"The best side draws the biggest crowds. The biggest crowds raise the biggest cheers."
"If you can't support us when we lose or draw, don't support us when we win."
"Liverpool was made for me and I was made for Liverpool."
"The man who said money can't buy you happiness has never been to Anfield."
"When I've got nothing better to do, I look down the league table to see how Everton are getting on."
"With him in the team, we could play Arthur Askey in goal."
"There are two great teams in Liverpool: Liverpool and Liverpool reserves."
"A football team is like a piano. You need eight men to carry it and three who can play the damn thing."
"Don't worry Alan. At least you'll be able to play next week."
"Football is the greatest game in the world and don't let anyone tell you any different."

## Brian Clough

"I wouldn't say I was the best manager in the business. But I was in the top one."
"We talk about it for twenty minutes and then we decide I was right."
"I like my women to be feminine, not sliding into tackles and covering every blade of grass on the pitch."
"On occasions I have been big-headed. I think most people are when they get in the limelight."
"They say Rome wasn't built in a day, but I wasn't on that particular job."
"Walk on water? I know most people out there will be saying that instead of walking on it, I should have taken more of it with my drinks."
"If God had wanted us to play football in the clouds, he'd have put grass up there."
"I want no epitaphs of profound history and all that type of thing. I contributed. I would hope they would say that, and I would hope somebody liked me."
"It only takes a second to score a goal."
"Don't send me flowers when I'm dead. If you like me, send them while I'm alive."
"Beckham? His wife can't sing and his barber can't cut hair."
"When you get the ball, pass it. When you receive the ball, control it. When you lose the ball, chase it."
"Rome wasn't built in a day, but I'm told Sunderland was."
"If a chairman sacks the manager he initially appointed, he should go as well."
"The River Trent is lovely, I know because I have walked on it for 18 years."
"I'd ask him how he thinks it should be done, we'd get into a discussion, and then we'd decide I was right."
"Players lose you games, not tactics. There's so much crap talked about tactics by people who barely know how to win at dominoes."
"The best team always wins. The rest is just gossip."
"We had a good team on paper. Unfortunately, the game was played on grass."
"Young man, when I want your opinion, I'll give it to you."
"You don't need to earn money to spend money."
"I once went missing in Nottingham for three months. Nobody noticed."
"We went unbeaten for 42 games at the City Ground. That's not bad for a small club."
"In this business, you've got to be a dictator or you haven't got a chance."
"Football hooligans? Well, there are 92 club chairmen for a start."

## Pelé

"Success is no accident. It is hard work, perseverance, learning, studying, sacrifice and most of all, love of what you are doing or learning to do."
"The more difficult the victory, the greater the happiness in winning."
"I was born to play football, just as Beethoven was born to write music and Michelangelo was born to paint."
"Football is the beautiful game."
"A penalty is a cowardly way to score."
"Everything is practice."
"Every kid around the world who plays football wants to be Pelé. I have a great responsibility to show them not just how to be like a football player, but how to be like a man."
"Enthusiasm is everything. It must be taut and vibrating like a guitar string."
"I am constantly being asked about individuals. The only way to win is as a team."
"I told myself before the game, 'he's made of skin and bones just like everyone else.'"
"I was born for football, just as Beethoven was born for music."
"Edson is the man. Pelé is the player."
"If I think of football as a religion, then the ball is God."
"There is always someone out there getting better than you by training harder than you."
"No individual can win a game by himself."

## Diego Maradona

"The ball doesn't get dirty."
"I am Maradona, who makes goals, who makes mistakes. I can take it all, I have shoulders big enough to fight with everybody."
"I have seen the player who will inherit my place in Argentine football and his name is Messi."
"When you've been to war, nothing scares you any more."
"If I could apologise and go back and change history I would do. But the goal is still a goal. Argentina became world champions and I was the best player in the world."
"I don't think I'm a legend. I'm just Diego from Villa Fiorito."
"To see the ball, to run after it, makes me the happiest man in the world."
"The goal was scored a little bit by the hand of God, another bit by the head of Maradona."
"My mother thinks I'm the best. And I was raised to always believe what my mother tells me."
"I always looked up to Pelé. He was my idol."
"When people succeed, it is because of hard work. Luck has nothing to do with success."
"There is no player in the world that can't be replaced."
"The World Cup is everything. It is the only thing."
"I gave everything on the pitch. Always. Every single time."
"I am black or white, I'll never be grey."

## Zlatan Ibrahimović

"An injured Zlatan is a pretty serious thing for any team."
"When you buy me, you are buying a Ferrari. If you drive a Ferrari you put premium fuel in the tank."
"I don't need the Ballon d'Or to know that I'm the best."
"I came like a king, left like a legend."
"One thing is for sure, a World Cup without me is nothing to watch."
"I'm not the kind of person to look back and have regrets."
"I can play in the 11 positions because a good player can play anywhere."
"Lions don't compare themselves to humans."
"Zlatan doesn't do auditions."
"I did not come to be a star. I came to be a legend."
"They said I was too old, too tall, too arrogant. Here I am."
"First I went left, he did too. Then I went right, and he did too. Then I went left again, and he went to buy a hot dog."
"We are looking for an apartment. If we don't find anything, we'll buy the hotel."
"I don't do cold. I'm from the Balkans."
"I'm like fine wine. I get better with age."
"I decide my future. I decide what I want to do. Nobody can push Zlatan."
"I didn't injure you. The ground did."
"A World Cup without Zlatan is not worth watching."
"People said I could never change, but look at me now."
"I admire Messi, but I don't admire the fact that he's better than me."

## Eric Cantona

"When the seagulls follow the trawler, it is because they think sardines will be thrown into the sea."
"I am searching for abstract ways of expressing reality, abstract forms that will enlighten my own mystery."
"I didn't study; I live."
"The real fans know what I was about."
"I have always been fascinated by the idea of commitment."
"In football, the worst blindness is only seeing the ball."
"I prefer to take risks, to go for it, and that's how I played."
"I am not a man, I am Cantona."
"He who is without sin, let him kick the first ball."
"My best moment? I have a lot of good moments but the one I prefer is when I kicked the hooligan."
"Art and football are the two most important things in the world."
"Sometimes when I'm alone, I think about football."
"The ball is round, the game is long, and in the end the beautiful always wins."
"Football is an art, like dancing is an art — but only when it's well done."
"You can change your wife, your politics, your religion, but never, never can you change your favourite football team."

## Zinedine Zidane

"I once cried because I had no shoes to play football, but one day I met a man who had no feet, and I realised how lucky I was."
"Am I afraid of death? No. It is the stake one puts up in order to play the game of life."
"Football is played on the field, not on paper."
"Every game I play is for the fans."
"I just play my game. It speaks for itself."
"Materazzi said something very personal about my mother and my sister."
"When you see a good player, you want to play with him."
"The ball is my best friend."
"To win, you have to believe that you can."
"I don't have any regrets. I've had an extraordinary career."

## Bobby Robson

"The first ninety minutes are the most important."
"We didn't underestimate them. They were a lot better than we thought."
"Home advantage gives you an advantage."
"I'm not going to look beyond the semi-final — but I would love to lead this team out at Wembley."
"If we start counting our chickens before they hatch, they won't lay any eggs."
"I do want to play the short ball and I do want to play the long ball. I think long and short balls is what football is all about."
"We don't want our players to be monks — we want them to be football players because a monk doesn't play football at this level."
"The game has gone mad. Three years ago you could tackle a player from behind and only get a yellow card. Now they've brought it in at halfway."
"People want success. It's like coffee, they want instant."
"I played cricket for my local village. It was 40 overs per side, and the weights of expectation were enormous."
"Look at those olive trees. They're over 200 years old and no one's watered them."
"What can I say about Peter Shilton? Peter Shilton is Peter Shilton, and I'll leave it at that."
"Anything from 1-0 to 2-0 would be a nice result."
"We mustn't be despondent. We don't have to play them every week — although we do play them every week."
"Gary Lineker has scored more goals in a major tournament than any player. Some players have scored as many, but Lineker is the one who's scored more."

## Bill Nicholson

"It is better to fail aiming high than to succeed aiming low. And we of Spurs have set our sights very high."
"When you lose, say little. When you win, say less."
"I want players who are prepared to suffer for the shirt."
"The game is about glory, it is about doing things in style."
"You are playing for the greatest club in the world."
"Always attack. Never sit back."
"A good side can score at any time."
"Football should be a spectacle. People come to be entertained."
"The great fallacy is that the game is first and last about winning."
"It's meant to be a great game, played by great players."
"""

TACTICAL_GLOSSARY = r"""# Football Tactical Encyclopedia

## Positions

### Goalkeeper (GK / Portero / Torwart / Gardien)
The last line of defence. Wears a distinct kit. Only player who may handle the ball inside their own penalty area. Modern goalkeepers are expected to be comfortable with the ball at their feet ("sweeper-keeper") and to act as a passing outlet during build-up play. Key attributes: shot-stopping, aerial command, distribution, communication, positioning.

### Centre-Back (CB / Central / Innenverteidiger / Défenseur central)
Positioned centrally in defence, typically in pairs or threes. Responsible for marking opposing strikers, winning aerial duels, and initiating build-up play. Modern CBs must be comfortable playing out from the back under pressure. Key attributes: heading, tackling, positioning, composure on the ball.

### Full-Back (RB/LB / Lateral / Außenverteidiger / Arrière latéral)
Positioned on either flank of the defensive line. Modern full-backs are expected to contribute offensively, overlapping wingers and delivering crosses. In Pep Guardiola's system, they often invert into midfield positions. Key attributes: pace, stamina, crossing, defensive awareness.

### Wing-Back (RWB/LWB)
A hybrid full-back/winger role used in 3-5-2 and 3-4-3 formations. Wing-backs cover the entire flank, requiring exceptional stamina. They must provide width in attack while tracking back to form a back five in defence. Key attributes: engine, crossing, positional intelligence, 1v1 defending.

### Sweeper (Libero)
A free-roaming defender behind the defensive line. Popularised by Franz Beckenbauer at Bayern Munich. The libero reads the game, mops up loose balls, and carries the ball forward to start attacks. Largely extinct in modern football due to the offside rule changes, but the concept lives on in ball-playing centre-backs.

### Defensive Midfielder (CDM / Pivote / Sechser / Sentinelle)
Sits in front of the defence, shielding the back line and breaking up opposition attacks. The "destroyer" type (e.g., Claude Makélélé, N'Golo Kanté) prioritises ball-winning. The "regista" type (e.g., Andrea Pirlo, Sergio Busquets) prioritises passing and orchestrating play. Key attributes: interceptions, passing, tactical intelligence, positioning.

### Central Midfielder (CM / Interior / Achter / Milieu central)
Box-to-box players who link defence and attack. Expected to contribute in both phases. Modern CMs must press, recover possession, carry the ball, and create chances. Key attributes: passing range, stamina, vision, tackling. Examples: Steven Gerrard, Patrick Vieira, Luka Modrić.

### Mezzala
An Italian term for a central midfielder who drifts wide, operating in the "half-spaces" between the centre and the flank. Used extensively in 3-5-2 systems. The mezzala creates numerical superiority in wide areas and arrives late in the box for goalscoring opportunities. Key attributes: dribbling, late runs, positional awareness.

### Attacking Midfielder (CAM / Enganche / Zehner / Meneur de jeu)
The classic "number 10" position. Operates between the opposition's midfield and defensive lines. Responsible for creating chances, playing through-balls, and linking midfield to attack. The role has evolved: pure playmakers are rarer, replaced by pressing forwards who can also create. Key attributes: vision, passing, dribbling, shooting.

### Trequartista
An Italian term for a free-roaming attacking midfielder or second striker. The trequartista has total creative freedom, drifting across the pitch to find pockets of space. Think Francesco Totti, Roberto Baggio, or Dennis Bergkamp. Key attributes: technical excellence, vision, unpredictability.

### Winger (RW/LW / Extremo / Flügelspieler / Ailier)
Wide attacking players who provide width, stretch defences, and deliver crosses or cut inside to shoot. Traditional wingers hug the touchline (e.g., Ryan Giggs). Inverted wingers play on their "wrong" side to cut inside onto their stronger foot (e.g., Arjen Robben). Key attributes: pace, dribbling, crossing, shooting.

### Striker / Centre-Forward (ST/CF / Delantero / Stürmer / Avant-centre)
The primary goalscorer. Types include: target man (physical, holds up play), poacher (predatory in the box), complete forward (combines all attributes). The role has evolved significantly — modern strikers must press from the front and contribute to build-up play. Key attributes: finishing, movement, hold-up play, pressing.

### False 9
A centre-forward who drops deep into midfield, dragging centre-backs out of position and creating space for teammates to exploit. Lionel Messi under Pep Guardiola at Barcelona is the most famous example. The role requires exceptional technical ability and football intelligence.

### Second Striker (SS / Seconda Punta / Media Punta)
Operates behind the main striker, linking play and arriving late in the box. Different from a number 10 in that the second striker is more goal-oriented and makes more runs in behind. Key attributes: movement, finishing, link-up play.

### Regista
A deep-lying playmaker who orchestrates the team's passing from a deep midfield position. The regista drops between or alongside the centre-backs to receive the ball and dictate the tempo. Andrea Pirlo is the archetypal regista. Key attributes: passing range, vision, composure, tactical intelligence.

### Carrilero
A central midfielder who shuttles up and down a narrow lateral channel ("carriles" = lanes in Spanish). Unlike a mezzala, the carrilero maintains discipline, rarely straying wide. Provides defensive cover and maintains the team's shape. Key attributes: stamina, positioning, discipline.

## Formations

### 4-4-2
The most traditional formation. Two banks of four with two strikers. Simple, balanced, and effective. Dominated English football for decades. Strengths: defensive solidity, clear structure, good width. Weaknesses: can be outnumbered in midfield by 4-3-3 or 4-5-1.

### 4-3-3
Three forwards with a central striker flanked by two wingers. The midfield triangle can point forward (one holding, two advanced) or backward (two holding, one advanced). Barcelona under Cruyff and Guardiola popularised the 4-3-3 with a single pivot. Strengths: width, pressing structure. Weaknesses: exposes full-backs if wingers don't track back.

### 3-5-2 / 3-4-1-2
Three centre-backs with two wing-backs providing width. Often transitions to a 5-3-2 defensively. Antonio Conte's Chelsea (2016-17) demonstrated its effectiveness in the Premier League. Strengths: defensive solidity with three CBs, numerical superiority in midfield. Weaknesses: relies heavily on wing-back fitness.

### 4-2-3-1
Dominant formation of the 2000s and 2010s. A double pivot protects the defence while an attacking trio operates behind a lone striker. Mourinho's Real Madrid and Germany's 2014 World Cup-winning team used this effectively. Strengths: balance, defensive security, creative freedom for the 10. Weaknesses: lone striker can be isolated.

### 4-1-4-1
A variation of 4-5-1 with a single defensive midfielder shielding the back four. The two central midfielders have license to advance. Defensive and counter-attacking shape. Strengths: compact, hard to break down. Weaknesses: limited attacking options if the midfielders don't push forward.

### 3-4-3
Three at the back with a midfield four and three forwards. Aggressive and attack-minded. Requires technically excellent centre-backs. Conte's Chelsea switch to 3-4-3 in 2016 transformed their season. Strengths: numerical superiority in attack, width from wing-backs. Weaknesses: vulnerable to counter-attacks through wide areas.

### WM Formation
Herbert Chapman's innovation at Arsenal in the 1930s. Named for the W-M shape players formed: three defenders, two half-backs forming the M; two inside-forwards and two wingers forming the W, with a centre-forward at the apex. Revolutionary for its time, it was the dominant system until the 1950s.

## Tactical Concepts

### Tiki-Taka
Short-passing, possession-based style associated with Barcelona and Spain (2008-2012). Emphasises ball retention, positional play, and patient build-up. Players constantly move to create passing triangles. The ball moves faster than any player can run. Critics argue it can become sterile if not paired with decisive vertical passes.

### Gegenpressing (Counter-pressing)
Immediately pressing to recover the ball after losing possession, rather than falling back into shape. Jürgen Klopp popularised this at Borussia Dortmund and Liverpool. The idea: the moment of transition is when the opponent is most disorganised. Press within 6 seconds of losing the ball.

### Total Football (Totaalvoetbal)
Dutch philosophy pioneered by Rinus Michels at Ajax and the Netherlands national team in the 1970s. Any outfield player can take over the role of any other player on the team. Requires extraordinary technical ability and tactical intelligence from every player. The pitch becomes fluid; positions become interchangeable.

### Catenaccio
Italian defensive system meaning "door-bolt." Uses a sweeper (libero) behind a tight defensive line. Associated with Helenio Herrera's Inter Milan in the 1960s. Often mischaracterised as purely negative — Herrera's Inter were devastating on the counter-attack. The philosophy: defend deep, protect the lead, strike on the break.

### High Press
Pressing the opposition high up the pitch, often in their own defensive third. Aims to force errors and win the ball close to the opponent's goal. Requires coordinated team pressing triggers (e.g., a backward pass, a poor touch). Risk: if beaten, large spaces open behind the press.

### Low Block
A deep defensive shape where both banks of players sit near their own penalty area. Aims to deny space, remain compact, and frustrate the opposition. Often paired with counter-attacking football. Tony Pulis, Diego Simeone, and José Mourinho are associated with effective low-block strategies.

### Positional Play (Juego de Posición)
Guardiola's adaptation of Cruyff's principles. The pitch is divided into zones; players occupy specific zones to maintain spacing and create passing options. The aim is to create numerical superiority in key zones. Principles: width, depth, support, mobility.

### Counter-Attacking Football
Deliberately conceding possession to the opposition, sitting deep, and striking rapidly when the ball is won. Requires fast, direct players who can transition quickly. Real Madrid under Mourinho (2011-12) and Leicester City under Claudio Ranieri (2015-16) are prime examples.

### Pressing Triggers
Specific situations that signal the team to press. Common triggers: a backward pass, a poor first touch, a switch of play to a weaker player, the ball entering a wide zone. Teams train specific pressing triggers to ensure coordinated pressure rather than individual chasing.

### Half-Spaces
The zones between the centre of the pitch and the wide areas. Exploiting half-spaces has become a key tactical concept in modern football. Players who drift into these areas are difficult to mark — they fall between the jurisdiction of the full-back and centre-back.

### Build-Up Play
The process of advancing the ball from defence into attacking areas. Modern build-up involves the goalkeeper and centre-backs passing through the opposition's press. Patterns include: goalkeeper to centre-back, centre-back splitting wide, full-backs pushing high, midfielder dropping to receive.

### Transition (Transición)
The moment a team switches between attack and defence (defensive transition) or defence and attack (attacking transition). The speed and quality of transitions often determine match outcomes. The best teams are devastating in transition moments.

### Set Pieces
Dead-ball situations: corners, free-kicks, throw-ins, penalties, goal-kicks. Modern teams dedicate significant training time to set pieces. Teams like Brentford and Brighton have used data-driven set-piece routines to gain a competitive advantage.

### Zonal Marking vs Man Marking
Two approaches to defending. Zonal marking: players defend specific areas of the pitch. Man marking: each defender is assigned a specific opponent. Most modern teams use a hybrid — zonal marking in open play with man-marking responsibilities at set pieces.

## Football Terminology in Multiple Languages

### English - Spanish - Portuguese - German - French - Italian - Dutch
Goal - Gol - Gol - Tor - But - Gol/Rete - Doelpunt
Offside - Fuera de juego - Impedimento - Abseits - Hors-jeu - Fuorigioco - Buitenspel
Corner kick - Saque de esquina - Escanteio - Ecke/Eckball - Corner - Calcio d'angolo - Hoekschop
Penalty - Penalti - Pênalti - Elfmeter - Penalty - Rigore/Calcio di rigore - Strafschop
Free kick - Tiro libre - Falta - Freistoß - Coup franc - Calcio di punizione - Vrije trap
Throw-in - Saque de banda - Arremesso lateral - Einwurf - Touche - Rimessa laterale - Inworp
Foul - Falta - Falta - Foul - Faute - Fallo - Overtreding
Yellow card - Tarjeta amarilla - Cartão amarelo - Gelbe Karte - Carton jaune - Cartellino giallo - Gele kaart
Red card - Tarjeta roja - Cartão vermelho - Rote Karte - Carton rouge - Cartellino rosso - Rode kaart
Dribble - Regate - Drible - Dribbling - Dribble - Dribbling - Dribbel
Header - Cabezazo - Cabeçada - Kopfball - Tête - Colpo di testa - Kopbal
Volley - Volea - Voleio - Volleyschuss - Volée - Tiro al volo - Volley

### Arabic: هدف (hadaf = goal), تسلل (tasallul = offside), ركلة جزاء (raklat jaza' = penalty)
### Japanese: ゴール (gōru = goal), オフサイド (ofusaido = offside), PK (pī kē = penalty kick)
### Turkish: Gol, Ofsayt, Penaltı, Korner, Faul, Sarı kart, Kırmızı kart
### Russian: Гол, Офсайд, Пенальти, Угловой, Фол, Жёлтая карточка, Красная карточка
### Polish: Gol, Spalony (offside), Rzut karny (penalty), Róg (corner), Faul
### Greek: Γκολ, Οφσάιντ, Πέναλτι, Κόρνερ, Φάουλ, Κίτρινη κάρτα, Κόκκινη κάρτα
### Hindi: गोल (goal), ऑफ़साइड (offside), पेनल्टी (penalty)
### Swahili: Bao (goal), Upande wa mbele (offside), Penalti (penalty)

## Famous Commentary Phrases

"GOOOOOL!" — Latin American commentary tradition, especially Andrés Cantor
"It's a goal! It's a goal!" — English commentary standard
"Tor! Tor! Tor!" — German commentary tradition
"And Solskjær has won it!" — Clive Tyldesley, 1999 Champions League Final
"They think it's all over... it is now!" — Kenneth Wolstenholme, 1966 World Cup Final
"Agüeroooooo!" — Martin Tyler, 2012 Premier League title decider
"The impossible has happened!" — Common in dramatic moments
"He could have hit it with his nose and it would have gone in." — Commentary cliché for tap-ins
"A worldie!" — Modern British slang for a spectacular goal
"He's sent the goalkeeper the wrong way." — Penalty commentary
"What a ball! What a finish!" — Generic celebration
"Unbelievable, Jeff!" — Chris Kamara, Soccer Saturday
"The magic of the cup!" — FA Cup commentary cliché
"They've pulled one back!" — Consolation goal commentary
"AND IT'S LIVE!" — Jeff Stelling, Soccer Saturday opening
"Welcome to the theater of dreams." — Old Trafford commentary
"This is Anfield." — Liverpool pre-match reference
"Golazo!" — Spanish for a brilliant goal
"Mamma mia!" — Italian exclamation for spectacular play
"What a hit, son! What a hit!" — Andy Gray, Sky Sports
"""

COMPETITION_HISTORIES = r"""# Competition Histories

## FIFA World Cup Winners (1930-2022)

1930: Uruguay (host: Uruguay) — beat Argentina 4-2 in final
1934: Italy (host: Italy) — beat Czechoslovakia 2-1 (a.e.t.)
1938: Italy (host: France) — beat Hungary 4-2
1950: Uruguay (host: Brazil) — beat Brazil 2-1 (final group stage)
1954: West Germany (host: Switzerland) — beat Hungary 3-2 ("Miracle of Bern")
1958: Brazil (host: Sweden) — beat Sweden 5-2 (17-year-old Pelé scores twice)
1962: Brazil (host: Chile) — beat Czechoslovakia 3-1
1966: England (host: England) — beat West Germany 4-2 (a.e.t.) ("They think it's all over")
1970: Brazil (host: Mexico) — beat Italy 4-1 (widely considered greatest team ever)
1974: West Germany (host: West Germany) — beat Netherlands 2-1
1978: Argentina (host: Argentina) — beat Netherlands 3-1 (a.e.t.)
1982: Italy (host: Spain) — beat West Germany 3-1 (Paolo Rossi 6 goals)
1986: Argentina (host: Mexico) — beat West Germany 3-2 (Maradona's tournament)
1990: West Germany (host: Italy) — beat Argentina 1-0 (Brehme penalty)
1994: Brazil (host: USA) — beat Italy on penalties (Baggio misses decisive kick)
1998: France (host: France) — beat Brazil 3-0 (Zidane heads twice)
2002: Brazil (host: Japan/South Korea) — beat Germany 2-0 (Ronaldo 8 goals)
2006: Italy (host: Germany) — beat France on penalties (Zidane headbutt)
2010: Spain (host: South Africa) — beat Netherlands 1-0 (a.e.t., Iniesta goal)
2014: Germany (host: Brazil) — beat Argentina 1-0 (a.e.t., Götze goal)
2018: France (host: Russia) — beat Croatia 4-2 (Mbappé breakthrough)
2022: Argentina (host: Qatar) — beat France on penalties (Messi's crowning glory)

World Cup top scorers all-time: Miroslav Klose (16), Ronaldo (15), Gerd Müller (14), Just Fontaine (13), Pelé (12)

## UEFA Champions League / European Cup Winners (1956-2024)

1956: Real Madrid, 1957: Real Madrid, 1958: Real Madrid, 1959: Real Madrid, 1960: Real Madrid, 1961: Benfica, 1962: Benfica, 1963: AC Milan, 1964: Inter Milan, 1965: Inter Milan, 1966: Real Madrid, 1967: Celtic, 1968: Manchester United, 1969: AC Milan, 1970: Feyenoord, 1971: Ajax, 1972: Ajax, 1973: Ajax, 1974: Bayern Munich, 1975: Bayern Munich, 1976: Bayern Munich, 1977: Liverpool, 1978: Liverpool, 1979: Nottingham Forest, 1980: Nottingham Forest, 1981: Liverpool, 1982: Aston Villa, 1983: Hamburg, 1984: Liverpool, 1985: Juventus, 1986: Steaua București, 1987: Porto, 1988: PSV Eindhoven, 1989: AC Milan, 1990: AC Milan, 1991: Red Star Belgrade, 1992: Barcelona, 1993: Marseille, 1994: AC Milan, 1995: Ajax, 1996: Juventus, 1997: Borussia Dortmund, 1998: Real Madrid, 1999: Manchester United, 2000: Real Madrid, 2001: Bayern Munich, 2002: Real Madrid, 2003: AC Milan, 2004: Porto, 2005: Liverpool, 2006: Barcelona, 2007: AC Milan, 2008: Manchester United, 2009: Barcelona, 2010: Inter Milan, 2011: Barcelona, 2012: Chelsea, 2013: Bayern Munich, 2014: Real Madrid, 2015: Barcelona, 2016: Real Madrid, 2017: Real Madrid, 2018: Real Madrid, 2019: Liverpool, 2020: Bayern Munich, 2021: Chelsea, 2022: Real Madrid, 2023: Manchester City, 2024: Real Madrid

Most wins: Real Madrid (15), AC Milan (7), Bayern Munich (6), Liverpool (6), Barcelona (5)

## Premier League Champions (1992-2024)

1993: Manchester United, 1994: Manchester United, 1995: Blackburn Rovers, 1996: Manchester United, 1997: Manchester United, 1998: Arsenal, 1999: Manchester United, 2000: Manchester United, 2001: Manchester United, 2002: Arsenal, 2003: Manchester United, 2004: Arsenal (Invincibles — unbeaten), 2005: Chelsea, 2006: Chelsea, 2007: Manchester United, 2008: Manchester United, 2009: Manchester United, 2010: Chelsea, 2011: Manchester United, 2012: Manchester City (Agüero moment), 2013: Manchester United, 2014: Manchester City, 2015: Chelsea, 2016: Leicester City (5000-1 miracle), 2017: Chelsea, 2018: Manchester City (100 points), 2019: Manchester City, 2020: Liverpool, 2021: Manchester City, 2022: Manchester City, 2023: Manchester City (Treble), 2024: Manchester City (4 in a row)

Most titles: Manchester United (13), Manchester City (8), Chelsea (5), Arsenal (3)

## La Liga Champions (selected 1929-2024)

Most titles: Real Madrid (36), Barcelona (27), Atletico Madrid (11), Athletic Bilbao (8), Valencia (6)

## Serie A Champions (selected 1898-2024)

Most titles: Juventus (36), Inter Milan (20), AC Milan (19), Genoa (9), Torino (7), Bologna (7)

## Bundesliga Champions (1963-2024)

Most titles: Bayern Munich (33), Borussia Dortmund (5), Borussia Mönchengladbach (5), Werder Bremen (4), Bayer Leverkusen (1)

## Copa América Winners (1916-2024)

Most titles: Argentina (16), Uruguay (15), Brazil (9), Chile (2), Paraguay (2), Peru (2), Colombia (1)

## Copa Libertadores Winners (1960-2024)

Most titles: Independiente (7), Boca Juniors (6), Peñarol (5), River Plate (4), Estudiantes (4), Santos (3), São Paulo (3), Nacional (3), Olimpia (3), Grêmio (3), Flamengo (3)

## UEFA European Championship Winners (1960-2024)

1960: Soviet Union, 1964: Spain, 1968: Italy, 1972: West Germany, 1976: Czechoslovakia, 1980: West Germany, 1984: France, 1988: Netherlands, 1992: Denmark, 1996: Germany, 2000: France, 2004: Greece, 2008: Spain, 2012: Spain, 2016: Portugal, 2020: Italy, 2024: Spain

Most wins: Germany/Spain (3 each), France/Italy (2 each)
"""

WORLD_CUP_COMPLETE = r"""# Complete World Cup History

## 1930 FIFA World Cup — Uruguay
Host: Uruguay. 13 teams participated. No qualification — all invited.
Final: Uruguay 4-2 Argentina (Estadio Centenario, Montevideo)
Top scorer: Guillermo Stábile (Argentina, 8 goals)
Notable: The first-ever World Cup. Several European teams declined to travel. Argentina led 2-1 at half-time before Uruguay's comeback. The golden era of South American football began.

## 1934 FIFA World Cup — Italy
Host: Italy (under Mussolini's fascist regime). 16 teams qualified.
Final: Italy 2-1 Czechoslovakia (a.e.t.) (Stadio Nazionale, Rome)
Top scorer: Oldřich Nejedlý (Czechoslovakia, 5 goals)
Notable: First World Cup with a qualification round. Heavily politicised by Mussolini. Defending champions Uruguay boycotted in retaliation for European teams snubbing 1930.

## 1938 FIFA World Cup — France
Host: France. 15 teams qualified.
Final: Italy 4-2 Hungary (Stade Olympique de Colombes, Paris)
Top scorer: Leônidas (Brazil, 7 goals)
Notable: Italy became first team to defend their title. Austria withdrew after German annexation. The last World Cup before WWII interrupted the tournament for 12 years.

## 1950 FIFA World Cup — Brazil
Host: Brazil. 13 teams (several withdrew).
Deciding match: Uruguay 2-1 Brazil (Maracanã, Rio de Janeiro — 199,854 attendance)
Top scorer: Ademir (Brazil, 8 goals)
Notable: The "Maracanazo." Brazil needed only a draw in the final group match but lost to Uruguay. The Maracanã fell silent. Goalkeeper Moacyr Barbosa was blamed for decades. No final per se — a final group round decided the winner.

## 1954 FIFA World Cup — Switzerland
Host: Switzerland. 16 teams.
Final: West Germany 3-2 Hungary (Wankdorf Stadium, Bern)
Top scorer: Sándor Kocsis (Hungary, 11 goals)
Notable: "The Miracle of Bern." Hungary's Mighty Magyars were unbeaten for 4 years and had thrashed Germany 8-3 in the group stage. Yet Germany came from 2-0 down to win 3-2. Highest-scoring World Cup ever (5.38 goals per game).

## 1958 FIFA World Cup — Sweden
Host: Sweden. 16 teams.
Final: Brazil 5-2 Sweden (Råsunda Stadium, Solna)
Top scorer: Just Fontaine (France, 13 goals — still the record for a single tournament)
Notable: 17-year-old Pelé announced himself to the world, scoring twice in the final. Brazil's first World Cup title. Just Fontaine's 13-goal haul remains unbroken.

## 1962 FIFA World Cup — Chile
Host: Chile. 16 teams.
Final: Brazil 3-1 Czechoslovakia (Estadio Nacional, Santiago)
Top scorer: Garrincha, Vavá, and 4 others (4 goals each)
Notable: Brazil won without the injured Pelé for most of the tournament. Garrincha was the star. The "Battle of Santiago" between Chile and Italy was one of the most violent matches in World Cup history.

## 1966 FIFA World Cup — England
Host: England. 16 teams.
Final: England 4-2 West Germany (a.e.t.) (Wembley Stadium, London)
Top scorer: Eusébio (Portugal, 9 goals)
Notable: "They think it's all over... it is now!" Geoff Hurst scored a hat-trick in the final — the only player ever to do so in a World Cup final. His controversial second goal (the ball hit the crossbar and bounced on/near the line) remains debated. North Korea sensationally beat Italy.

## 1970 FIFA World Cup — Mexico
Host: Mexico. 16 teams.
Final: Brazil 4-1 Italy (Estadio Azteca, Mexico City)
Top scorer: Gerd Müller (West Germany, 10 goals)
Notable: Widely considered the greatest World Cup and the greatest team. Brazil's 1970 side — Pelé, Jairzinho, Tostão, Gérson, Rivelino — played breathtaking football. Carlos Alberto's final goal is considered the greatest team goal ever. Brazil kept the Jules Rimet trophy permanently after winning it three times.

## 1974 FIFA World Cup — West Germany
Host: West Germany. 16 teams.
Final: West Germany 2-1 Netherlands (Olympiastadion, Munich)
Top scorer: Grzegorz Lato (Poland, 7 goals)
Notable: The Netherlands introduced Total Football to the world. Johan Cruyff and his team dazzled with fluid, interchangeable positions. The Dutch won a penalty before a German player touched the ball in the final, but West Germany recovered to win. The "Cruyff Turn" was born.

## 1978 FIFA World Cup — Argentina
Host: Argentina (under military junta). 16 teams.
Final: Argentina 3-1 Netherlands (a.e.t.) (Estadio Monumental, Buenos Aires)
Top scorer: Mario Kempes (Argentina, 6 goals)
Notable: Politically controversial — Argentina's military dictatorship used the tournament for propaganda. Mario Kempes was the hero, scoring twice in the final. The ticker-tape atmosphere of the Monumental became iconic. Netherlands lost their second consecutive final.

## 1982 FIFA World Cup — Spain
Host: Spain. 24 teams (expanded from 16).
Final: Italy 3-1 West Germany (Santiago Bernabéu, Madrid)
Top scorer: Paolo Rossi (Italy, 6 goals — Golden Boot)
Notable: Paolo Rossi's redemption — returning from a match-fixing ban to win the Golden Boot and inspire Italy's triumph. Brazil's 1982 team (Zico, Sócrates, Falcão) played the most beautiful football but were eliminated by Italy. The greatest World Cup for purists.

## 1986 FIFA World Cup — Mexico
Host: Mexico. 24 teams.
Final: Argentina 3-2 West Germany (Estadio Azteca, Mexico City)
Top scorer: Gary Lineker (England, 6 goals)
Notable: Diego Maradona's tournament. The "Hand of God" and "Goal of the Century" both came in the quarter-final against England. Maradona was unstoppable, dragging Argentina to glory almost single-handedly. Many consider this the greatest individual tournament performance ever.

## 1990 FIFA World Cup — Italy
Host: Italy. 24 teams.
Final: West Germany 1-0 Argentina (Stadio Olimpico, Rome)
Top scorer: Salvatore Schillaci (Italy, 6 goals)
Notable: Widely considered the worst World Cup for quality of football. Defensive, cynical play dominated. Argentina had two players sent off in the final. Andreas Brehme's penalty was the only goal. Cameroon's run to the quarter-finals (led by 38-year-old Roger Milla) was a highlight.

## 1994 FIFA World Cup — USA
Host: United States. 24 teams.
Final: Brazil 0-0 Italy (a.e.t., Brazil won 3-2 on penalties) (Rose Bowl, Pasadena)
Top scorer: Oleg Salenko (Russia) and Hristo Stoichkov (Bulgaria), 6 goals each
Notable: The first World Cup decided by a penalty shootout. Roberto Baggio's missed penalty for Italy remains one of football's most iconic images. The tournament helped popularise football in America. Maradona was sent home after failing a drug test.

## 1998 FIFA World Cup — France
Host: France. 32 teams (expanded from 24).
Final: France 3-0 Brazil (Stade de France, Saint-Denis)
Top scorer: Davor Šuker (Croatia, 6 goals)
Notable: Host nation France won, led by Zinedine Zidane's two headers in the final. Ronaldo's mysterious illness before the final remains one of football's great mysteries. Michael Owen's wonder goal against Argentina. Croatia finished third in their first World Cup as an independent nation.

## 2002 FIFA World Cup — Japan/South Korea
Host: Japan and South Korea. 32 teams.
Final: Brazil 2-0 Germany (International Stadium, Yokohama)
Top scorer: Ronaldo (Brazil, 8 goals)
Notable: First World Cup in Asia. Ronaldo's redemption after the 1998 final trauma. South Korea's run to the semi-finals amid refereeing controversies. Turkey finished third. Senegal beat France in the opening match. Oliver Kahn won the Golden Ball despite playing in the losing side.

## 2006 FIFA World Cup — Germany
Host: Germany. 32 teams.
Final: Italy 1-1 France (a.e.t., Italy won 5-3 on penalties) (Olympiastadion, Berlin)
Top scorer: Miroslav Klose (Germany, 5 goals)
Notable: Zinedine Zidane's headbutt on Marco Materazzi in the final defined the tournament. Italy won their fourth World Cup. Zidane won the Golden Ball despite his red card. The "Summer Fairy Tale" in Germany — a festival atmosphere throughout.

## 2010 FIFA World Cup — South Africa
Host: South Africa. 32 teams.
Final: Spain 1-0 Netherlands (a.e.t.) (Soccer City, Johannesburg)
Top scorer: Thomas Müller, David Villa, Wesley Sneijder, Diego Forlán (5 goals each)
Notable: First World Cup in Africa. The vuvuzela became iconic. Spain won their first World Cup, completing an unprecedented Euro-World Cup-Euro treble (2008-2012). Andrés Iniesta scored the winning goal in the 116th minute. Diego Forlán won the Golden Ball.

## 2014 FIFA World Cup — Brazil
Host: Brazil. 32 teams.
Final: Germany 1-0 Argentina (a.e.t.) (Maracanã, Rio de Janeiro)
Top scorer: James Rodríguez (Colombia, 6 goals)
Notable: Germany's 7-1 demolition of Brazil in the semi-final — the "Mineirazo" — was the most stunning result in World Cup history. Mario Götze scored the winner in the final. Lionel Messi won the Golden Ball but couldn't lift the trophy. Tim Howard set a record 16 saves for USA vs Belgium.

## 2018 FIFA World Cup — Russia
Host: Russia. 32 teams.
Final: France 4-2 Croatia (Luzhniki Stadium, Moscow)
Top scorer: Harry Kane (England, 6 goals)
Notable: France won their second title, powered by 19-year-old Kylian Mbappé who became the youngest scorer in a World Cup final since Pelé. Croatia's remarkable run to the final — winning three knockout matches after extra time. VAR was used for the first time. Iceland and Panama made their World Cup debuts.

## 2022 FIFA World Cup — Qatar
Host: Qatar. 32 teams.
Final: Argentina 3-3 France (a.e.t., Argentina won 4-2 on penalties) (Lusail Stadium)
Top scorer: Kylian Mbappé (France, 8 goals)
Notable: Widely regarded as the greatest World Cup final ever. Lionel Messi finally won the World Cup at age 35, cementing his legacy. Mbappé scored a hat-trick in the final — the first since Geoff Hurst in 1966. The first winter World Cup (November-December). Morocco became the first African nation to reach a semi-final. Saudi Arabia's shock victory over Argentina in the group stage.
"""

MANAGER_PHILOSOPHIES = r"""# Manager Philosophies

## Sir Alex Ferguson (1941-)
Club career: East Stirlingshire, St Mirren, Aberdeen, Manchester United (1986-2013)

Sir Alex Ferguson is the most successful British football manager in history. His 26-year reign at Manchester United is unparalleled in the modern game. Ferguson's philosophy was never tied to a single tactical system — he was the ultimate pragmatist who adapted his approach based on the players available and the opposition faced.

Ferguson's core principles were: relentless winning mentality, the ability to rebuild teams across generations, promoting youth (the "Class of '92"), and an unshakeable belief that the game is never over until the final whistle (hence "Fergie Time"). He built four distinct great teams: the 1993-94 double winners, the 1999 Treble side, the 2007-08 Champions League winners, and the 2012-13 title winners.

His management style combined intimidation (the famous "hairdryer treatment") with genuine care for his players. He controlled the narrative through mind games, press conferences, and his mastery of the media. Ferguson understood that managing a football club was about much more than tactics — it was about culture, discipline, standards, and creating an environment where winning was the only acceptable outcome.

## Pep Guardiola (1971-)
Club career: Barcelona (2008-2012), Bayern Munich (2013-2016), Manchester City (2016-)

Pep Guardiola is the most influential tactical mind of the 21st century. A disciple of Johan Cruyff, Guardiola took Cruyff's principles — possession, positional play, pressing — and refined them into a coherent, revolutionary system that changed how football is played worldwide.

At Barcelona, Guardiola created arguably the greatest club team in history. His 2008-2012 Barcelona won 14 trophies in four seasons, playing a brand of football that mesmerised the world. The false 9 Messi, the possession stranglehold, the six-second rule for pressing — all became Guardiola hallmarks.

At Bayern Munich, he refined his ideas further, introducing "juego de posición" (positional play) in its purest form. His full-backs inverted into midfield, his wingers stayed wide, and his teams created numerical superiority in every zone. At Manchester City, he adapted again — introducing a more direct style while maintaining his core principles. His City side has dominated English football, winning multiple Premier League titles and the 2023 Treble.

Guardiola's football is built on five principles: (1) create numerical superiority, (2) maintain proper spacing across the pitch, (3) move the ball faster than the opponent can shift, (4) press immediately upon losing the ball, (5) attack through the centre and half-spaces.

## José Mourinho (1963-)
Club career: Benfica, Leiria, Porto, Chelsea, Inter Milan, Real Madrid, Chelsea, Manchester United, Tottenham, Roma, Fenerbahçe

José Mourinho is the great contrarian of modern football. While Guardiola preaches possession, Mourinho preaches pragmatism. His philosophy: the result matters above all else. Mourinho's teams are built on defensive organisation, collective sacrifice, and devastating counter-attacks.

At Porto, he won the 2004 Champions League with a team that had no business beating the continent's elite. At Chelsea, he created the most defensively solid team the Premier League has ever seen (2004-05: 15 goals conceded in 38 games). At Inter Milan, he won the 2010 Treble with a masterclass in tactical flexibility — his Inter beat Barcelona in the Champions League semi-final with a defensive performance for the ages.

Mourinho's approach involves: (1) making his team extremely difficult to beat, (2) creating a siege mentality ("us against the world"), (3) exploiting the opposition's weaknesses rather than imposing his own style, (4) being willing to play ugly if necessary, (5) winning the psychological battle before the tactical one.

## Jürgen Klopp (1967-)
Club career: Mainz 05, Borussia Dortmund (2008-2015), Liverpool (2015-2024)

Jürgen Klopp transformed two clubs into European giants and popularised gegenpressing for a global audience. His philosophy: football should be emotional, intense, and entertaining. "Heavy metal football" — all-out attack, relentless pressing, and raw passion.

At Borussia Dortmund, Klopp built a team that broke Bayern Munich's stranglehold on the Bundesliga, winning consecutive titles (2010-11, 2011-12) and reaching the 2013 Champions League final. His Dortmund played with extraordinary energy, pressing opponents into submission and attacking with breathtaking speed.

At Liverpool, Klopp recreated the magic on an even grander scale. He built a team around the devastating front three of Salah, Mané, and Firmino, the creative full-backs Alexander-Arnold and Robertson, and the midfield engine of Henderson, Fabinho, and Wijnaldum. Liverpool won the Champions League (2019), Premier League (2020), FA Cup, League Cup, and FIFA Club World Cup under Klopp.

Klopp's core principles: (1) gegenpressing — win the ball back within 6-8 seconds of losing it, (2) direct, vertical football — no sideways passing for the sake of it, (3) high defensive line — compress the pitch, (4) emotional connection — the manager, players, and fans must be as one, (5) tactical flexibility — Klopp adapted from 4-2-3-1 to 4-3-3 to suit his squad.

## Johan Cruyff (1947-2016)
Playing career: Ajax, Barcelona. Managerial career: Ajax, Barcelona (1988-1996)

Johan Cruyff was not just a footballer or a manager — he was a philosopher who happened to work in football. His ideas, built on the foundations of Rinus Michels' Total Football, shaped the way Barcelona, Ajax, and indeed modern football itself are played.

As Barcelona manager (1988-1996), Cruyff created the "Dream Team" and established the playing philosophy that persists at the club to this day. His 3-4-3 formation was revolutionary, with ball-playing defenders, creative midfielders, and intelligent forwards who pressed and passed their way to four consecutive La Liga titles (1991-94) and the club's first European Cup (1992).

Cruyff's principles: (1) the pitch must be made as large as possible in possession and as small as possible out of possession, (2) every player must be comfortable with the ball, including the goalkeeper, (3) football should be beautiful and entertaining, (4) youth development is paramount — he created La Masia's philosophy, (5) speed of thought matters more than speed of legs.

## Arrigo Sacchi (1946-)
Club career: AC Milan (1987-1991), Italy national team (1991-1996)

Arrigo Sacchi revolutionised Italian football by rejecting catenaccio in favour of high pressing, zonal marking, and coordinated team defending. His AC Milan (1987-1991) is often cited as the greatest club team in European football history alongside Guardiola's Barcelona.

Sacchi was the first modern manager to treat the team as a unit of 11 players working in unison. His Milan pressed as a team, attacked as a team, and defended as a team. The offside trap was executed with military precision. His back four of Tassotti, Baresi, Costacurta, and Maldini could step up in perfect synchronisation to catch attackers offside.

Sacchi's innovation was twofold: (1) he proved that a team could be greater than the sum of its parts, and (2) he showed that pressing could be a form of attack. His Milan won back-to-back European Cups (1989, 1990), demolishing Real Madrid 5-0 and Steaua București 4-0 along the way.

## Rinus Michels (1928-2005)
Club career: Ajax (1965-1971), Barcelona, Netherlands national team

The "General" — Rinus Michels is the architect of Total Football. At Ajax in the late 1960s and early 1970s, Michels created a system where every outfield player could play in every position. The concept was revolutionary: football was not about 11 individuals in fixed positions but about 11 intelligent players who could adapt fluidly to any situation.

Michels' Ajax won three consecutive European Cups (1971-73), and his Netherlands team reached the 1974 World Cup final playing the most beautiful football the world had seen. The principles were simple in theory, impossible in execution without the right players: (1) interchange of positions, (2) pressing the ball, not the man, (3) creating space through movement, (4) maintaining possession as the foundation of everything.

## Brian Clough (1935-2004)
Club career: Hartlepool United, Derby County, Brighton, Leeds United, Nottingham Forest (1975-1993)

Brian Clough's achievements at Nottingham Forest remain among the most remarkable in football history. He took a second-division club and, within three years, won the First Division title (1977-78), the European Cup (1979), and then defended the European Cup the following year (1980). No English club has matched this trajectory.

Clough's philosophy was deceptively simple: play good, passing football, give the ball to your best players, and trust your instincts. He was a supreme man-manager who could get ordinary players to perform extraordinary feats. His partnership with Peter Taylor was essential — Taylor scouted the players, Clough managed them.

His approach: (1) keep it simple — short passes, good movement, (2) the manager's word is law, (3) character matters as much as ability, (4) winning with style, (5) never fear anyone, regardless of reputation.

## Bill Shankly (1913-1981)
Club career: Carlisle United, Grimsby Town, Workington, Huddersfield Town, Liverpool (1959-1974)

Bill Shankly built modern Liverpool. When he arrived in 1959, Liverpool were in the Second Division, playing in front of sparse crowds at a dilapidated Anfield. By the time he retired in 1974, Liverpool were the dominant force in English football, Anfield was a fortress, and the Kop was the most famous stand in world football.

Shankly's philosophy was rooted in socialism, hard work, and collective spirit. Football was simple: pass and move, press the ball, play for the team. He transformed Liverpool's culture from the ground up, rebuilding the training ground, the scouting network, and most importantly, the mentality.

His legacy: the Boot Room tradition, the pass-and-move style, the never-say-die mentality, and the unbreakable bond between club and city. Bob Paisley, Joe Fagan, Kenny Dalglish, and all subsequent Liverpool managers inherited Shankly's foundation.

## Marcelo Bielsa (1955-)
Club career: Newell's Old Boys, Atlas, América, Vélez Sársfield, Espanyol, Argentina, Chile, Athletic Bilbao, Marseille, Lille, Leeds United, Uruguay

Marcelo Bielsa is football's ultimate idealist. His influence on the modern game is enormous — Guardiola has called him "the best manager in the world." Bielsa's teams press relentlessly, attack fearlessly, and play with an intensity that is physically unsustainable over a full season. And Bielsa doesn't care.

His philosophy: (1) the team must press the ball at all times, in all areas of the pitch, (2) attack is the best form of defence, (3) players must give everything — "Bielsa burnout" is a known phenomenon, (4) preparation is paramount — his pre-match analysis is legendarily detailed, (5) football should be a spectacle.

## Diego Simeone (1970-)
Club career: Racing Club, Atlético Madrid (2011-)

Diego Simeone turned Atletico Madrid from perennial underachievers into one of Europe's most formidable teams. His philosophy is the antithesis of Guardiola's: defend deep, fight for every ball, and win ugly if necessary. Simeone's Atletico are built on defensive organisation, collective sacrifice, and an almost religious work ethic.

His achievements — La Liga titles in 2014 and 2021, two Champions League finals — were accomplished with a fraction of the budget available to Barcelona and Real Madrid. Simeone proved that identity and mentality can overcome financial disparity.

## Carlo Ancelotti (1959-)
Club career: Reggiana, Parma, Juventus, AC Milan, Chelsea, PSG, Real Madrid, Bayern Munich, Napoli, Everton, Real Madrid

Carlo Ancelotti is the most decorated manager in Champions League history. His secret: man-management. While other managers obsess over tactical details, Ancelotti focuses on relationships, trust, and creating an environment where elite players can thrive.

His philosophy is pragmatic flexibility: he adapts to his players rather than forcing them into a rigid system. At Milan, he played 4-3-2-1 (the "Christmas tree"). At Real Madrid, he used 4-3-3, 4-4-2, and everything in between. Ancelotti's calm, empathetic demeanour belies a fierce competitive instinct.

## Arsène Wenger (1949-)
Club career: Nancy, Monaco, Nagoya Grampus Eight, Arsenal (1996-2018)

Arsène Wenger transformed English football. When he arrived at Arsenal in 1996, the Premier League was built on physicality, long balls, and pre-match pints. Wenger introduced continental sophistication: dietary science, detailed training regimes, technical football, and a scouting network that unearthed gems from around the world.

His Arsenal side of 2003-04 — "The Invincibles" — went the entire Premier League season unbeaten, a feat not achieved since Preston North End in 1889. Wenger's football was beautiful, fast, and direct, built on the technical excellence of players like Bergkamp, Henry, Pirès, and Vieira.

## Bobby Robson (1933-2009)
Club career: Fulham, Ipswich Town, England, PSV Eindhoven, Sporting CP, Porto, Barcelona, Newcastle United

Sir Bobby Robson was the people's manager. Universally loved for his warmth, passion, and humanity, Robson was also a tactical innovator who won league titles in three countries and reached a World Cup semi-final with England (1990).

His philosophy: football should be played with joy. Robson built teams on a foundation of hard work and togetherness, but always with an emphasis on creativity and attacking intent. He nurtured young players — Ronaldo, Mourinho, Guardiola, and Robson himself all credit Bobby Robson as a formative influence.

## Matt Busby (1909-1994)
Club career: Manchester United (1945-1969, 1970-71)

Sir Matt Busby created the modern Manchester United. He built three great teams: the 1948 FA Cup winners, the "Busby Babes" of the 1950s, and the 1968 European Cup winners. The Munich air disaster of 1958 killed eight of his Babes, but Busby survived, rebuilt, and led United to European Cup glory a decade later — the first English club to win it.

Busby's philosophy: youth, adventure, and entertainment. He promoted young players, attacked relentlessly, and believed that football should inspire. His legacy — the attacking tradition, the youth academy, the global ambition — defines Manchester United to this day.

## Helenio Herrera (1910-1997)
Club career: Various Spanish clubs, Inter Milan (1960-1968), Roma

The "Mago" (Wizard) — Helenio Herrera is synonymous with catenaccio, the ultra-defensive Italian system. At Inter Milan in the 1960s, Herrera perfected the art of defensive football, winning two European Cups (1964, 1965) and three Serie A titles.

But Herrera was more complex than his caricature suggests. He was one of the first managers to emphasise physical conditioning, mental preparation, and squad management. His team talks were legendary, and he pioneered the concept of a pre-match "ritiro" (retreat).

## Telê Santana (1931-2006)
Club career: Various Brazilian clubs, Brazil national team (1980-1982, 1985-1986), São Paulo

Telê Santana managed the Brazil teams of 1982 and 1986 — two of the most beautiful sides that never won a World Cup. His 1982 team (Zico, Sócrates, Falcão, Éder, Cerezo) is widely considered the greatest team never to win the tournament.

Santana's philosophy was quintessentially Brazilian: skill, creativity, and joy. He refused to compromise his attacking ideals, even when pragmatism might have delivered results. Later, at São Paulo, he won back-to-back Club World Cups (1992, 1993), proving that beautiful football could also be winning football.

## Valeri Lobanovsky (1939-2002)
Club career: Dynamo Kyiv (multiple spells), Soviet Union, UAE, Kuwait

Valeri Lobanovsky was decades ahead of his time. At Dynamo Kyiv and with the Soviet Union, he treated football as a science — using computers, data analysis, and physical conditioning long before "analytics" became a buzzword. His Dynamo Kyiv won the European Cup Winners' Cup in 1975 and 1986 and reached the 1988 Euro final with the Soviet Union.

Lobanovsky's philosophy: football is a system of 22 players and one ball, governed by mathematical principles. Every movement should serve a tactical purpose. Every player must be supremely fit. The team is paramount; the individual is secondary. His ideas directly influenced the modern analytical approach.

## Ernst Happel (1925-1992)
Club career: Feyenoord, Club Brugge, Hamburger SV, Netherlands national team, Austria Vienna

Ernst Happel is the only manager to win the European Cup with two different clubs (Feyenoord 1970, Hamburg 1983). He also took the Netherlands to the 1978 World Cup final and Club Brugge to the 1978 European Cup final. A tactical innovator, Happel pioneered pressing football and zonal marking in an era of man-marking.

## Viktor Maslov (1910-1977)
Club career: Torpedo Moscow, Dynamo Kyiv (1964-1970)

Viktor Maslov is one of football's forgotten geniuses. At Dynamo Kyiv in the 1960s, he pioneered the 4-4-2 formation, high pressing, and the use of midfield pressing to win the ball in advanced positions — concepts that would not become mainstream in Western European football for another 20 years. Maslov's ideas directly influenced Lobanovsky, who played under him at Dynamo Kyiv.
"""

ANALYTICS_DEEP_DIVES = r"""# Football Analytics Revolution

## Expected Goals (xG)

Expected Goals (xG) is the metric that has most transformed how we understand football. xG assigns a probability (between 0 and 1) to every shot, representing the likelihood of that shot resulting in a goal based on historical data.

Factors that influence xG include: distance from goal, angle to goal, body part used (foot, head, other), type of assist (through ball, cross, cutback), game state, whether the shot followed a dribble, number of defenders between the shooter and goal, goalkeeper position.

A penalty has an xG of approximately 0.76. A shot from the centre of the box, 8 yards out, with no defenders blocking, might have an xG of 0.30. A shot from 30 yards has an xG of approximately 0.03.

Teams that consistently outperform their xG (scoring more goals than expected) are considered clinically efficient. Teams that underperform are likely to regress. Over a full season, xG is one of the most reliable predictors of future performance — more reliable than actual goals scored.

Key insight: xG strips away the noise of luck and finishing variance to reveal the true quality of chances created and conceded. A team creating 2.0 xG per game but only scoring 1.0 is likely to improve. A team creating 0.8 xG but scoring 1.5 is riding luck.

## Expected Assists (xA)

xA measures the likelihood that a given pass will result in an assist. It evaluates the quality of the chance created by the passer, independent of whether the receiver scores. A through ball that puts a striker one-on-one with the goalkeeper has a high xA; a cross into a crowded penalty area has a lower xA.

xA is valuable for evaluating creative players: a midfielder who creates high-xA chances is genuinely dangerous, even if his striker keeps missing. Over time, xA identifies the true creative force in a team.

## Passes Per Defensive Action (PPDA)

PPDA measures pressing intensity. It counts the number of passes a team allows the opposition to make before making a defensive action (tackle, interception, or foul) in the opposition's half.

Lower PPDA = more intense pressing. A team with a PPDA of 6 is pressing aggressively; a team with a PPDA of 15 is sitting deep. Liverpool under Klopp regularly posted PPDA values around 7-9. Burnley under Sean Dyche were typically 14-16.

PPDA has become a standard metric for evaluating tactical approach: it tells you objectively whether a team is pressing high or sitting deep, removing the subjectivity of the eye test.

## Progressive Passes and Progressive Carries

A progressive pass moves the ball significantly closer to the opponent's goal. Specifically, a pass that moves the ball at least 10 yards toward the goal (or any pass into the penalty area) counts as progressive. Progressive carries work similarly but measure ball carries (dribbles) rather than passes.

These metrics identify players who advance the ball effectively — the line-breakers, the creators, the ball-progressors who move the ball from safe areas into dangerous ones. Trent Alexander-Arnold, for instance, consistently ranks among the top full-backs in Europe for progressive passes, reflecting his role as Liverpool's primary creative outlet from deep.

## How Liverpool Used Data Under Klopp

Liverpool's data revolution under sporting director Michael Edwards and head of research Ian Graham transformed the club from mid-table mediocrity to Champions League and Premier League champions.

Key decisions driven by data:
1. Signing Mohamed Salah (data identified him as significantly undervalued at Roma)
2. Signing Andy Robertson (the most productive left-back in Scotland, available for £8m)
3. Signing Virgil van Dijk (data confirmed he was the best ball-playing centre-back available)
4. Selling Philippe Coutinho to Barcelona for £142m and reinvesting in Alisson and Van Dijk
5. Identifying Fabinho as the ideal defensive midfielder for Klopp's system

Liverpool's approach combined traditional scouting with sophisticated data modelling. They didn't just look at goals and assists — they measured pressing intensity, ball recoveries, progressive actions, and spatial data to identify players who would fit Klopp's gegenpressing system.

## How Manchester City Use Data Under Guardiola

Manchester City's analytics department is one of the most advanced in world football. Under the direction of the City Football Group's data science team, City use tracking data, event data, and custom metrics to inform tactical decisions, recruitment, and in-game adjustments.

Key aspects of City's data approach:
1. Positional data: City track player positions 25 times per second using GPS and optical tracking. This allows them to measure spacing, compactness, and positional discipline — all central to Guardiola's positional play philosophy.
2. Expected Threat (xT): City use expected threat models to evaluate how much a player's actions increase the probability of a goal. This measures the value of every pass, carry, and dribble — not just the ones that end in shots.
3. Pressing models: City's data team quantifies pressing effectiveness, measuring not just how often players press but how effectively they do so — press success rate, subsequent ball recovery location, and chances created from turnovers.
4. Set-piece analysis: City dedicate significant analytical resources to set pieces, identifying opponent vulnerabilities from corners, free-kicks, and throw-ins.

## Brighton and Brentford Analytics Models

Brighton & Hove Albion and Brentford represent two of the most data-driven clubs in English football.

Brighton, under technical director David Weir and their data team, have built a recruitment model that consistently identifies undervalued players. Their approach involves buying players for their underlying performance data (expected metrics, ball progression, pressing) rather than their output (goals, assists). Players like Moisés Caicedo, Marc Cucurella, and Alexis Mac Allister were signed for modest fees and sold for enormous profits.

Brentford's model, pioneered by owner Matthew Benham (who also owns a sports analytics company), focuses on statistical arbitrage in the transfer market. Brentford buy players whose data profiles suggest they are undervalued by the market, develop them, and sell for a profit. Their set-piece routines are data-driven — Brentford have been one of the most effective set-piece teams in the Premier League.

## StatsBomb Open Data Revolution

StatsBomb, founded by Ted Knutson in 2017, has transformed football analytics by providing detailed event data that goes far beyond traditional statistics. Their open data — freely available datasets from specific competitions — has democratised football analytics, allowing researchers, journalists, and fans to work with professional-grade data.

StatsBomb's innovations include: freeze-frame data (showing the position of every player at the moment of a shot), detailed pressure events, 360-degree data showing the full context of every action, and custom metrics like shot-creating actions and goal-creating actions.

## How Transfermarkt Values Are Calculated

Transfermarkt, the German football database, has become the standard reference for player market values. Their system combines algorithmic estimation with crowdsourced community input. Factors include: age, contract length, performance data, league strength, recent transfer fees for comparable players, and market demand.

The values are not transfer fees — they are estimates of fair market value. Actual transfer fees can be significantly higher (demand exceeds supply) or lower (player has a short contract, wants to leave, or is out of favour). Transfermarkt values correlate strongly with actual transfer fees but are systematically lower for elite players, whose fees include a premium.

## Modern Scouting with Wyscout and InStat

Wyscout and InStat are the two dominant platforms for professional football scouting. Both provide comprehensive video and data for thousands of leagues worldwide, allowing scouts and analysts to evaluate players remotely before committing to in-person scouting trips.

Wyscout offers event data (passes, shots, tackles, etc.), video clips tagged to each event, and comparison tools that allow analysts to rank players across leagues. InStat provides similar functionality with a focus on Eastern European and Asian markets.

The modern scouting workflow: (1) data screening — use analytics to identify a long list of candidates matching specific performance criteria, (2) video analysis — watch tagged clips on Wyscout/InStat to evaluate technical quality, decision-making, and physical attributes, (3) in-person scouting — attend matches to assess intangibles: personality, effort, body language, (4) final evaluation — combine all sources to make a recommendation.
"""

FOOTBALL_LANGUAGES = r"""# Football in 15 Languages

## English (England, worldwide)
Key terms: match, pitch, kit, boots, cap (international appearance), clean sheet, hat-trick, derby, relegation, promotion, stoppage time, injury time, extra time, penalty shootout, golden goal (historical), the beautiful game, a brace (two goals), woodwork (hitting the post/bar), a worldie (spectacular goal), a thunderbolt (powerful shot), nutmeg (ball through legs), a tap-in (easy goal)
Chants: "You'll Never Walk Alone" (Liverpool), "Glory Glory Man United", "North London Forever", "Blue is the Colour", "Swing Low Sweet Chariot" (No — that's rugby! This is football only), "When the Spurs Go Marching In"
Commentary style: Understated, building to crescendo. "And it's in! What a goal!" The English style often features dry wit and historical references.
Unique concept: "The magic of the FA Cup" — the romanticised belief that cup competitions create upsets and fairy tales.

## Spanish (Spain, Latin America)
Key terms: gol, portero (goalkeeper), delantero (striker), mediocampista (midfielder), defensa (defender), tiro (shot), pase (pass), falta (foul), fuera de juego (offside), córner, penalti, prórroga (extra time), tanda de penaltis (penalty shootout), goleada (heavy defeat), golazo (brilliant goal), chilena (bicycle kick), rabona, sombrero (chip over defender), caño (nutmeg), tiki-taka
Chants: "Yo soy español, español, español" (Spain), "Dale campeón" (Argentina), "Olé olé olé" (universal)
Commentary style: Passionate, extended "GOOOOL!" calls (Andrés Cantor tradition). Latin American commentary is theatrical, emotional, and celebratory. Spanish commentary is slightly more restrained but equally passionate.
Unique concept: "La garra" (the claw) — Uruguayan concept of fighting spirit. "Gambeta" — Argentine term for elegant dribbling.

## Portuguese (Brazil, Portugal)
Key terms: gol, goleiro (goalkeeper - Brazil) / guarda-redes (Portugal), atacante (attacker), zagueiro (centre-back), lateral (full-back), passe, chute (shot), falta, impedimento (offside), escanteio (corner), pênalti, prorrogação (extra time), goleada, golaço (brilliant goal), drible, chapéu (sombrero/chip), caneta (nutmeg - Brazil), trivela (outside-of-the-foot technique)
Chants: "É campeão!" "Olê olê olê olá!" "Eu te amo [club name]!" "Vamos [club name]!"
Commentary style: Brazilian commentary is the most exuberant in the world. Extended calls, singing, poetry. "GOOOOOL DO BRASIL!" Portuguese commentary is more European — passionate but controlled.
Unique concepts: "Jogo bonito" (the beautiful game - Brazil), "Ginga" (the rhythmic, dance-like quality of Brazilian football), "Malícia" (cunning/street-smartness), "Raça" (grit/determination - Portugal)

## German (Germany, Austria, Switzerland)
Key terms: Tor (goal), Torwart (goalkeeper), Stürmer (striker), Mittelfeldspieler (midfielder), Verteidiger (defender), Schuss (shot), Pass, Foul, Abseits (offside), Ecke (corner), Elfmeter (penalty - literally "eleven-meter"), Verlängerung (extra time), Elfmeterschießen (penalty shootout), Nachspielzeit (stoppage time), Fallrückzieher (bicycle kick), Doppelpack (brace), Meisterschale (championship trophy)
Chants: "Deutscher Meister BVB!" "Stern des Südens" (Bayern), "54, 74, 90, 2006" (World Cup years)
Commentary style: Technical, analytical, with moments of pure excitement. "Tor! Tor! Tor!" German commentators provide detailed tactical analysis mixed with emotional calls.
Unique concepts: "Ordnung" (order/discipline), "Mannschaft" (team - also the national team's nickname), "Meister der Herzen" (champion of hearts - moral victory)

## French (France, Africa, worldwide)
Key terms: but (goal), gardien de but (goalkeeper), attaquant (striker), milieu de terrain (midfielder), défenseur (defender), tir (shot), passe, faute (foul), hors-jeu (offside), corner, penalty/pénalty, prolongation (extra time), tirs au but (penalty shootout), lucarne (top corner - literally "skylight"), petit pont (nutmeg - literally "small bridge"), ciseau retourné (bicycle kick), une-deux (one-two pass)
Chants: "Allez les Bleus!" "On est les champions!" "La Marseillaise" (national anthem, sung at matches)
Commentary style: Eloquent and literary. French commentary often features poetic descriptions and philosophical observations about the game. African Francophone commentary adds tremendous passion and musicality.
Unique concepts: "Le petit pont" (nutmeg), "La lucarne" (top corner), "Le Classique" (PSG vs Marseille)

## Italian (Italy)
Key terms: gol/rete (goal), portiere (goalkeeper), attaccante (striker), centrocampista (midfielder), difensore (defender), tiro (shot), passaggio (pass), fallo (foul), fuorigioco (offside), calcio d'angolo (corner), rigore (penalty), supplementari (extra time), calci di rigore (penalty shootout), rovesciata (bicycle kick), tunnel (nutmeg), cucchiaio (Panenka - literally "spoon"), fantasista (creative playmaker)
Chants: "Forza [club name]!" "Alé alé alé!" "Siamo noi, siamo noi, i campioni dell'Italia siamo noi!"
Commentary style: Operatic. Italian commentary features dramatic pauses, rising intensity, and the famous drawn-out call. "GOOOOOOL! Che gol! Che meraviglia!" Italian pundits provide deep tactical analysis.
Unique concepts: "Fantasista" (creative genius), "Calciopoli" (match-fixing scandal), "Catenaccio" (defensive system), "Zona Cesarini" (late drama, after Renato Cesarini), "Trequartista" (behind-the-striker role)

## Dutch (Netherlands, Belgium)
Key terms: doelpunt (goal), keeper (goalkeeper), spits (striker), middenvelder (midfielder), verdediger (defender), schot (shot), pass, overtreding (foul), buitenspel (offside), hoekschop (corner), strafschop (penalty), verlenging (extra time), strafschoppenserie (penalty shootout), omhaal (bicycle kick), panna (nutmeg), brilstand (0-0 draw - literally "glasses score")
Chants: "Hup Holland Hup!" "Wij houden van Oranje!" "De Kampioenen!"
Commentary style: Direct, passionate, analytical. Dutch commentary features tactical insight and honest (sometimes brutally so) assessment. Commentators are expected to be informed and opinionated.
Unique concepts: "Totaalvoetbal" (Total Football), "Oranje" (the colour/national team), "Branie" (audacious swagger)

## Arabic (Middle East, North Africa)
Key terms: هدف (hadaf = goal), حارس المرمى (haris al-marma = goalkeeper), مهاجم (muhajem = striker), لاعب وسط (la'eb wasat = midfielder), مدافع (mudafe' = defender), تسديدة (tasdida = shot), تمريرة (tamrira = pass), مخالفة (mukhalafa = foul), تسلل (tasallul = offside), ركنية (rukniya = corner), ركلة جزاء (raklat jaza' = penalty), ديربي (derby), هاتريك (hat-trick)
Commentary style: Among the most passionate in the world. Arabic football commentary is an art form — rhythmic, poetic, and intensely emotional. Commentators like Issam El-Shawali and Raouf Khlif have millions of followers for their iconic calls.
Unique concept: "La'eb" (skillful player), used as the 2022 World Cup mascot name

## Japanese (Japan)
Key terms: ゴール (gōru = goal), GK/ゴールキーパー (goalkeeper), FW/フォワード (forward), MF/ミッドフィルダー (midfielder), DF/ディフェンダー (defender), シュート (shūto = shot), パス (pasu = pass), ファウル (fauru = foul), オフサイド (ofusaido = offside), PK/ペナルティーキック (penalty kick), 延長戦 (enchōsen = extra time), サポーター (sapōtā = supporter/fan)
Commentary style: Respectful, technical, building to explosive celebrations. "GOOOOORRUUU!" Japanese commentary combines polite analysis with genuine excitement. Fan culture is orderly but passionate.
Unique concepts: "J-League" culture — fans clean up the stadium after matches (a practice that became globally famous at the 2018 and 2022 World Cups)

## Turkish (Turkey)
Key terms: Gol, kaleci (goalkeeper), forvet (striker), orta saha (midfielder), defans (defender), şut (shot), pas (pass), faul (foul), ofsayt (offside), korner (corner), penaltı (penalty), uzatma (extra time), penaltı atışları (penalty shootout), röveşata (bicycle kick), çalım (dribbling move), derbi
Chants: "Cimbom!" (Galatasaray), "En büyük [club name]!" "Şampiyon [club name]!"
Commentary style: Intense and emotional. Turkish commentary reflects the passionate fan culture. Goals are met with extended calls, and derbies are covered with enormous intensity.
Unique concept: "Amigo" (the fan who leads chants with a megaphone from the stands)

## Russian (Russia)
Key terms: Гол (gol = goal), вратарь (vratar' = goalkeeper), нападающий (napadayushchiy = striker), полузащитник (poluzashchitnik = midfielder), защитник (zashchitnik = defender), удар (udar = shot), пас (pas = pass), фол (fol = foul), офсайд (ofsayd = offside), угловой (uglovoy = corner), пенальти (penal'ti = penalty), дополнительное время (dopolnitel'noye vremya = extra time)
Commentary style: Deep, analytical, with a tradition of eloquent description. Soviet-era commentary was formal; modern Russian commentary is more emotional and personality-driven.

## Polish (Poland)
Key terms: Gol/bramka (goal), bramkarz (goalkeeper), napastnik (striker), pomocnik (midfielder), obrońca (defender), strzał (shot), podanie (pass), faul (foul), spalony (offside), rzut rożny (corner), rzut karny (penalty), dogrywka (extra time), seria rzutów karnych (penalty shootout)
Commentary style: Passionate, building with the play. Polish commentators use rich vocabulary and are known for extended goal calls and emotional reactions.

## Greek (Greece)
Key terms: Γκολ (gkol = goal), τερματοφύλακας (termatofylakas = goalkeeper), επιθετικός (epithetikos = striker), μέσος (mesos = midfielder), αμυντικός (amyntikos = defender), σουτ (sout = shot), πάσα (pasa = pass), φάουλ (faoul = foul), οφσάιντ (ofsaint = offside), κόρνερ (korner = corner), πέναλτι (penalti = penalty), ντέρμπι (nterbi = derby)
Commentary style: Highly emotional. Greek football commentary reflects the intense passion of Greek football culture, particularly during Athens derbies and European nights.
Unique concept: "Thyra 7" (Gate 7 - Olympiacos ultras), the intensity of Greek derby culture

## Hindi (India)
Key terms: गोल (goal), गोलकीपर (goalkeeper), स्ट्राइकर (striker), मिडफ़ील्डर (midfielder), डिफ़ेंडर (defender), शॉट (shot), पास (pass), फ़ाउल (foul), ऑफ़साइड (offside), कॉर्नर (corner), पेनल्टी (penalty)
Commentary style: Energetic, growing rapidly with ISL and EPL broadcasting. Indian football commentary often switches between Hindi and English, reflecting the bilingual nature of Indian football fandom.

## Swahili (East Africa)
Key terms: Bao (goal), kipa (goalkeeper, from "keeper"), mshambuliaji (striker), kiungo (midfielder), beki (defender, from "back"), mpira (ball/football), kona (corner), penalti (penalty), upande wa mbele (offside), kadi ya njano (yellow card), kadi nyekundu (red card), mchezo (match/game)
Commentary style: Rhythmic and community-oriented. East African football commentary often features call-and-response patterns and colourful local expressions.
Unique concept: Football as community — in East Africa, football is not just sport but social fabric, with local derbies carrying enormous cultural significance
"""


def _write_hardcoded_files(corpus_dir: Path) -> list[dict]:
    """Write all hardcoded corpus files and return manifest entries."""
    files = {
        "football_wisdom.txt": FOOTBALL_WISDOM,
        "tactical_glossary.txt": TACTICAL_GLOSSARY,
        "competition_histories.txt": COMPETITION_HISTORIES,
        "world_cup_complete_history.txt": WORLD_CUP_COMPLETE,
        "manager_philosophies.txt": MANAGER_PHILOSOPHIES,
        "analytics_deep_dives.txt": ANALYTICS_DEEP_DIVES,
        "football_languages.txt": FOOTBALL_LANGUAGES,
    }
    entries: list[dict] = []
    for filename, content in files.items():
        content = content.strip()
        path = corpus_dir / filename
        path.write_text(content, encoding="utf-8")
        word_count = len(content.split())
        entries.append({
            "doc_id": filename.replace(".txt", ""),
            "title": filename.replace(".txt", "").replace("_", " ").title(),
            "category": "hardcoded",
            "word_count": word_count,
            "generated_at": datetime.now(UTC).isoformat(),
        })
        logger.info("Wrote %s (%d words)", filename, word_count)
    return entries


_HARDCODED_FILENAMES = [
    "football_wisdom.txt",
    "tactical_glossary.txt",
    "competition_histories.txt",
    "world_cup_complete_history.txt",
    "manager_philosophies.txt",
    "analytics_deep_dives.txt",
    "football_languages.txt",
]


def _read_existing_hardcoded(corpus_dir: Path) -> list[dict]:
    """Build manifest entries from hardcoded files already on disk."""
    entries: list[dict] = []
    for filename in _HARDCODED_FILENAMES:
        path = corpus_dir / filename
        if not path.exists():
            logger.warning("Expected hardcoded file missing: %s", path)
            continue
        text = path.read_text(encoding="utf-8")
        word_count = len(text.split())
        entries.append({
            "doc_id": filename.replace(".txt", ""),
            "title": filename.replace(".txt", "").replace("_", " ").title(),
            "category": "hardcoded",
            "word_count": word_count,
            "generated_at": datetime.now(UTC).isoformat(),
        })
        logger.info("Found %s (%d words)", filename, word_count)
    return entries


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def fetch_wikipedia_articles(
    corpus_dir: Path,
    max_workers: int = 10,
    delay: float = 1.0,
) -> tuple[list[dict], list[str], list[str]]:
    """Fetch Wikipedia articles in batches. Returns (manifest_entries, failed, skipped)."""
    titles = _all_titles()
    logger.info("Total unique Wikipedia titles: %d", len(titles))

    manifest: list[dict] = []
    failed: list[str] = []
    skipped: list[str] = []
    doc_counter = 0

    batch_size = max_workers
    for batch_start in range(0, len(titles), batch_size):
        batch = titles[batch_start : batch_start + batch_size]
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_fetch_article, t): t for t in batch}
            for future in as_completed(futures):
                title, text = future.result()
                if text is None:
                    if _is_gridiron(""):
                        skipped.append(title)
                    else:
                        failed.append(title)
                    continue

                filename = f"wiki_{doc_counter:05d}.txt"
                (corpus_dir / filename).write_text(text, encoding="utf-8")
                manifest.append({
                    "doc_id": filename.replace(".txt", ""),
                    "title": title.replace("_", " "),
                    "category": "wikipedia",
                    "word_count": len(text.split()),
                    "generated_at": datetime.now(UTC).isoformat(),
                })
                doc_counter += 1

        done = batch_start + len(batch)
        logger.info(
            "Progress: %d / %d titles processed (%d fetched, %d failed, %d skipped)",
            done, len(titles), doc_counter, len(failed), len(skipped),
        )
        if done < len(titles):
            time.sleep(delay)

    return manifest, failed, skipped


def generate_football_corpus(
    output_dir: str | Path | None = None,
    wiki_only: bool = False,
) -> None:
    """Generate the complete football corpus.

    Args:
        output_dir: Where to write corpus files. Defaults to data/corpus/.
        wiki_only: If True, skip hardcoded file generation (they're already in the repo)
                   and build manifest from existing hardcoded files + fresh wiki fetches.
    """
    default_path = Path(__file__).resolve().parent.parent / "data" / "corpus"
    corpus_dir = Path(output_dir) if output_dir else default_path
    corpus_dir.mkdir(parents=True, exist_ok=True)

    # 1. Hardcoded files
    if wiki_only:
        logger.info("--wiki-only: reading existing hardcoded files from repo...")
        hardcoded_entries = _read_existing_hardcoded(corpus_dir)
    else:
        logger.info("Writing hardcoded knowledge files...")
        hardcoded_entries = _write_hardcoded_files(corpus_dir)

    # 2. Fetch Wikipedia articles
    logger.info("Fetching Wikipedia articles (10 threads, 1s delay between batches)...")
    wiki_entries, failed, skipped = fetch_wikipedia_articles(corpus_dir)

    # 3. Write manifest
    all_entries = hardcoded_entries + wiki_entries
    manifest_path = corpus_dir / "manifest.jsonl"
    with manifest_path.open("w", encoding="utf-8") as f:
        for entry in all_entries:
            f.write(json.dumps(entry) + "\n")

    # 4. Write failures log
    if failed or skipped:
        fail_path = corpus_dir / "failed_articles.txt"
        with fail_path.open("w", encoding="utf-8") as f:
            if failed:
                f.write("=== FAILED (could not fetch) ===\n")
                for t in sorted(failed):
                    f.write(t + "\n")
            if skipped:
                f.write("\n=== SKIPPED (American football detected) ===\n")
                for t in sorted(skipped):
                    f.write(t + "\n")

    # 5. Summary
    total_words = sum(e["word_count"] for e in all_entries)
    logger.info("=" * 60)
    logger.info("CORPUS GENERATION COMPLETE")
    logger.info("Hardcoded files:    %d", len(hardcoded_entries))
    logger.info("Wikipedia articles: %d", len(wiki_entries))
    logger.info("Total documents:    %d", len(all_entries))
    logger.info("Total words:        %d", total_words)
    logger.info("Failed fetches:     %d", len(failed))
    logger.info("Skipped (gridiron): %d", len(skipped))
    logger.info("Manifest: %s", manifest_path)
    logger.info("=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate association football corpus")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory")
    parser.add_argument(
        "--wiki-only",
        action="store_true",
        help="Skip hardcoded file generation (use files already in repo)",
    )
    args = parser.parse_args()
    generate_football_corpus(output_dir=args.output_dir, wiki_only=args.wiki_only)
