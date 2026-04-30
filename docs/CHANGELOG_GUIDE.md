# Changelog Schrijfgids

Template en richtlijnen voor het schrijven van changelog-teksten die gebruikers te zien krijgen in de app.

## Database velden

| Veld | Voorbeeld | Toelichting |
|------|-----------|-------------|
| `version` | `1.2.0` | Semantic versioning (major.minor.patch) |
| `title` | `Bug reports, link bibliotheek & verbeterde interface` | Korte samenvatting, max ~60 karakters |
| `content_html` | Zie template hieronder | HTML die in de changelog modal verschijnt |

---

## Template

```html
<h3 style="margin:0 0 6px;font-size:1rem;">🎉 Sectie titel</h3>
<p style="margin:0 0 14px;color:#8b8fa3;font-size:0.9rem;">
  Beschrijving in 1-2 zinnen. Gebruik <strong>bold</strong> voor knoppen of pagina-namen.
</p>

<h3 style="margin:0 0 6px;font-size:1rem;">✨ Sectie met lijst</h3>
<ul style="margin:0 0 14px;padding-left:1.2rem;color:#8b8fa3;font-size:0.9rem;">
  <li>Punt één</li>
  <li>Punt twee</li>
  <li>Punt drie</li>
</ul>
```

### Inline styles (verplicht)

De changelog modal heeft geen eigen stylesheet, dus alle styling gaat inline:

- **`<h3>`** → `margin:0 0 6px;font-size:1rem;`
- **`<p>`** → `margin:0 0 14px;color:#8b8fa3;font-size:0.9rem;`
- **`<ul>`** → `margin:0 0 14px;padding-left:1.2rem;color:#8b8fa3;font-size:0.9rem;`
- Laatste element: gebruik `margin:0` i.p.v. `margin:0 0 14px` om extra ruimte onderaan te voorkomen.

---

## Schrijfregels

1. **Schrijf voor eindgebruikers**, niet voor developers. Geen bestandsnamen, geen git-termen.
2. **Begin elke sectie met een emoji** — maakt het scanbaar en vriendelijk.
3. **Gebruik `<p>` voor uitleg**, `<ul>` voor opsommingen van meerdere kleine punten.
4. **Houd het kort** — max 5-6 secties. De modal is niet groot.
5. **Leg uit wat het doet**, niet hoe het werkt. "Klik op de bug-knop rechtsonder" > "FAB component met modal".
6. **Gebruik `<strong>`** om knoppen, pagina's of acties te highlighten.
7. **Nederlandse tekst**, tenzij de app meertalig wordt.

---

## Handige emoji's per categorie

| Categorie | Emoji's |
|-----------|---------|
| Nieuwe feature | 🎉 ✨ 🆕 🚀 |
| Verbetering | ⚡ 📝 🔧 💡 |
| Bug fix | 🐛 🩹 🔨 |
| UI/Design | 🎨 💅 🖼️ |
| Links/SEO | 🔗 🔍 📊 |
| Vertaling | 🌍 🗣️ |
| Afbeeldingen | 🖼️ 📸 |
| Systeem/Infra | ⚙️ 🗞️ 🛡️ |

---

## Voorbeeld (v1.2.0)

```html
<h3 style="margin:0 0 6px;font-size:1rem;">🐛 Bugs melden is nu makkelijk</h3>
<p style="margin:0 0 14px;color:#8b8fa3;font-size:0.9rem;">
  Zie je iets raars of heb je een idee? Klik op de <strong>bug-knop</strong> rechtsonder
  in het scherm. Je kunt kiezen uit categorieën zoals Bug, Feature of UI/Design en
  direct feedback sturen.
</p>

<h3 style="margin:0 0 6px;font-size:1rem;">🔗 Link Bibliotheek</h3>
<p style="margin:0 0 14px;color:#8b8fa3;font-size:0.9rem;">
  Voeg je eigen links toe in het <strong>Genereer</strong>-formulier. Deze links worden
  meegegeven aan de AI zodat er automatisch relevante interne links in je blogpost
  worden verwerkt.
</p>

<h3 style="margin:0 0 6px;font-size:1rem;">📝 Formulier verbeteringen</h3>
<ul style="margin:0 0 14px;padding-left:1.2rem;color:#8b8fa3;font-size:0.9rem;">
  <li>Betere indeling van het genereer-formulier — alles overzichtelijker</li>
  <li>WordPress-categorie en tag-support bij publiceren</li>
  <li>Publicatie jobs tonen nu meer details en waarschuwingen</li>
</ul>

<h3 style="margin:0 0 6px;font-size:1rem;">⚡ Snellere &amp; stabielere app</h3>
<ul style="margin:0 0 14px;padding-left:1.2rem;color:#8b8fa3;font-size:0.9rem;">
  <li>De hele interface laadt nu efficiënter door modulaire code</li>
  <li>Ongebruikte code opgeruimd voor betere performance</li>
  <li>Diverse kleine bugfixes in de interface</li>
</ul>

<h3 style="margin:0 0 6px;font-size:1rem;">🗞️ Changelog popup</h3>
<p style="margin:0;color:#8b8fa3;font-size:0.9rem;">
  Vanaf nu krijg je bij elke update automatisch dit venster te zien zodat je altijd
  op de hoogte bent van wat er nieuw is.
</p>
```

---

## Toevoegen aan de app

Via het **Admin panel** → Changelogs sectie, of direct in de database:

```sql
INSERT INTO changelogs (version, title, content_html, created_by, published, created_at)
VALUES ('1.2.0', 'Bug reports, link bibliotheek & verbeterde interface', '<h3 style="...">...</h3>...', 1, 1, NOW());
```

De changelog verschijnt automatisch als popup bij gebruikers die hem nog niet gezien hebben.
