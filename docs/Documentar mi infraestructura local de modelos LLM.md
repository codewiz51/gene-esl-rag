# Documentar mi infraestructura local de modelos LLM

## Cómo uso LLMs para producir lecciones de inglés como segunda lengua

Tengo la suerte de contar con hardware capaz de ejecutar LLMs en local.

### Hardware de cómputo

- **Mac Studio M4 Max** con 36 GB de memoria unificada. Lo compré originalmente para editar video. De haber sabido que iba a ejecutar modelos LLM en local, habría comprado más memoria unificada.
- **MacBook Pro** con M3 Pro y 18 GB de memoria unificada. Igual, lo compré para editar video. De haber tenido la menor idea de que iba a usar Exo para compartir y ejecutar LLMs de forma distribuida, habría comprado más memoria.
- También tengo un viejo **Mac Mini de 2014 con Intel i7 de cuatro núcleos**, con 16 GB de RAM. Lo uso para almacenamiento en red. Mis nietos le sacan provecho para entretenerse con YouTube.
- La red local usa un switch Netgear de 1 Gb. La conexión a internet la manejan los routers Eero y la fibra de 2 Gb de Dobson. El Studio y el MacBook también van conectados con un cable Thunderbolt 4 (40 Gb/s) cuando ejecutan tareas como las que usa Exo.
- Mirando hacia atrás, todo se ve claro.

Estoy jubilado y sigo desarrollando software para iOS, sitios web Razor y código en Python.

Este es el software en el que me he quedado para el desarrollo con LLMs:

- **Ollama** ← Mi servidor LLM de cabecera.
- **LM Studio** ← Requiere más memoria de la que me conviene; solo lo uso de vez en cuando.
- **AnythingLLM** ← Es mi cliente de confianza para todo lo de Ollama.
- **ChromaDB** ← Este es mi RAG secundario.
- **LanceDB** ← Este es mi RAG principal.
- **Python 3**
- **Pandoc**
- Alrededor de 80 librerías y apps más de Homebrew.
- Tengo suscripción a **Brave Search**. Por la forma en que uso los LLMs, rara vez me paso de 5 a 10 búsquedas por semana.
- **Exo** para inferencia distribuida usando el Studio y el MacBook.

Van a notar que, a lo largo de esta serie de artículos, me refiero a **LLMs**, no a "IA". ¿Por qué? Porque cuando usas IA lo suficiente, te topas con los errores que se cometen por: suposiciones incorrectas —tanto de humanos como de software—, prompts mal hechos, deriva del modelo, alucinaciones, salvaguardas mal configuradas y demasiada confianza de nuestra parte. Y te das cuenta de que, al final, es un emparejamiento estadístico a gran escala, determinado por parámetros y tensores, y con cero intuición. Así que, para mí, son LLMs. Lo que hacen es reducir el trabajo pesado que me tomaría horas replicar a mano.

También me suscribí al plan **Office 365 Familiar**, que me da acceso a Copilot con la suscripción Premium de M365. Tengo suscripción a **Anthropic**, y uso Claude y Claude Code. Y todavía tengo una suscripción a **Gemini**. Todos tienen su uso, pero me estoy alejando de M365 y de Gemini. Uso Claude para ayudarme con el desarrollo de prompts. Un hábito que sigo de forma constante, ya sea que use un LLM en la nube o uno local, es pedirle al modelo que resuelva discrepancias y contradicciones entre el prompt, la información de fondo que tiene y lo que quizás necesite de aquí en adelante. Generalmente intento recopilar información pertinente y cargarla en la base de datos vectorial para reducir la necesidad de búsquedas en línea.

Eso es todo por este primer post. Voy a presentar las lecciones futuras con un estilo de "marinero borracho" (*drunken sailor*).

---

**Actualización 9 de septiembre** — He desinstalado ChromaDB; ya no es mi base de datos vectorial secundaria. Ahora tengo una instancia de LanceDB independiente de AnythingLLM. También uso la versión de LanceDB que viene integrada en AnythingLLM. El contenido de las dos instancias de LanceDB no está sincronizado.

**Aclaración sobre las suscripciones de Office 365:** Originalmente me suscribí al plan Office 365 Familiar y a Copilot Pro. Microsoft ofreció una migración a Office 365 que combinó mis suscripciones de Copilot Pro y Office 365 en una sola.
