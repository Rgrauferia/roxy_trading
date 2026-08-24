# Roxy Renueva

Roxy Renueva is a private module inside Roxy Home. It does not share photos,
memory, API keys, budgets, or permissions with Trading, Crypto, Finance, or
Study.

## User flow

1. Open **Hoy → Roxy Renueva → Crear proyecto**.
2. Add a current room photo, room type, style, budget, measurements, objects to
   preserve, and priorities.
3. Roxy stores the project under the authenticated Home member only.
4. **Crear propuesta visual** edits the uploaded room photograph. The prompt
   explicitly preserves the architecture, camera angle, fixed elements, and
   requested belongings.
5. Select suggested furnishing categories and choose **Buscar productos
   reales**. Roxy prepares the existing commerce handoff; the user must confirm
   before leaving for Amazon, Walmart, Target, or another configured retailer.

Prices, stock, brands, and dimensions are not fabricated. They are confirmed
on the retailer page. Roxy never stores retailer passwords or payment cards and
never completes payment.

## Server configuration

```dotenv
ROXY_HOME_DESIGN_PATH=data/roxy_home_design.json
ROXY_HOME_DESIGN_IMAGE_DIR=data/roxy_home_design
ROXY_HOME_DESIGN_IMAGE_QUALITY=low
ROXY_HOME_OPENAI_API_KEY=...
ROXY_HOME_OPENAI_DEEP_MODEL=gpt-5.6-terra
```

The OpenAI key is server-only. The implementation uses the Responses API with
`store=false` and the `image_generation` tool. On Render, both design paths
must live on the existing persistent Home disk.

Deleting a project deletes its original room photo and generated proposal.
