# Vertex AI Setup (Imagen Generate + Edit)

Deze handleiding legt uit hoe je Vertex AI correct instelt voor:
- Nieuwe afbeeldingen genereren met Imagen
- Bestaande afbeeldingen aanpassen met Imagen Edit

De app is geconfigureerd voor:
- Generate: imagen-3.0-generate-002
- Edit: imagen-3.0-capability-001

## 1. Vereisten in Google Cloud

1. Open je Google Cloud project.
2. Zorg dat billing actief is.
3. Enable APIs:
   - Vertex AI API
   - IAM Service Account Credentials API
4. Controleer regio support (aanbevolen: us-central1).

## 2. Service account maken

1. Ga naar IAM & Admin > Service Accounts.
2. Maak een service account aan (of gebruik bestaande).
3. Geef minimaal de juiste rechten voor Vertex AI gebruik.
   - Praktisch startpunt: Vertex AI User
4. Maak een JSON key aan:
   - Keys > Add key > Create new key > JSON
5. Sla het JSON bestand veilig lokaal op.

## 3. .env instellen

Vul in je .env de volgende velden in:

OPENAI_API_KEY=...
MASTER_KEY=...
VERTEX_PROJECT_ID=jouw-project-id
VERTEX_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=C:/pad/naar/service-account.json
OPENAI_TEXT_MODEL=gpt-4o
IMAGEN_MODEL=imagen-3.0-generate-002
IMAGEN_EDIT_MODEL=imagen-3.0-capability-001

Opmerking:
- Gebruik forward slashes of escaped backslashes in paden op Windows.
- De app gebruikt Vertex OAuth via service account credentials.

## 4. App starten

1. Installeer dependencies:
   pip install -r requirements.txt
2. Start de app:
   python run.py
3. Let op startup log:
   - Vertex auth startup check OK

Als je die regel ziet, is Vertex auth goed.

## 5. Functionele test

1. Genereer een nieuwe afbeelding.
2. Regenereren met feedback (image edit).
3. Verwachte logs:
   - Generate via imagen-3.0-generate-002
   - Edit via imagen-3.0-capability-001

## 6. Bekende fouten en oplossingen

### Fout: Invalid JWT Signature

Mogelijke oorzaken:
- Verkeerde JSON key
- Ingetrokken/vervangen key
- Verkeerd pad in GOOGLE_APPLICATION_CREDENTIALS
- Systeemklok niet gesynchroniseerd

Acties:
1. Genereer een nieuwe JSON key in IAM.
2. Update GOOGLE_APPLICATION_CREDENTIALS.
3. Herstart app.
4. Controleer Windows tijdsync (admin rechten kunnen nodig zijn).

### Fout: model unavailable (404)

Voorbeeld:
- imagen-3.0-capability-002 is unavailable

Oplossing:
- Gebruik IMAGEN_EDIT_MODEL=imagen-3.0-capability-001

### Fout: Must provide at least one context_image

Dit wijst meestal op een onjuiste edit payload-structuur.
In deze codebase is dat al aangepast naar de juiste Vertex Imagen edit structuur met referenceImages.

## 7. Productie-aanbevelingen

- Gebruik geen development server in productie.
- Beperk service account rechten tot minimum nodig.
- Roteer keys periodiek.
- Bewaar JSON key buiten de repo.
- Zet secrets alleen in .env (niet committen).

## 8. Snelle checklist

- Vertex AI API enabled
- Service account met juiste rol
- Geldige, actieve JSON key
- .env variabelen correct
- VERTEX_LOCATION ondersteund
- Startup log toont: Vertex auth startup check OK
