# Connection conventions seen in the sample architectures

What the engineers' approved drawings show about how things connect. These are **observations, not client-confirmed rules**; they
are what the model is told to follow when the prompt does not say otherwise, and every such connection is marked `assumed` and
listed in the diagram's notes. The sample drawings were used only to learn structure, grouping and connections; none of their
pictures is used (decision D30).

| Pattern | Seen in | What it shows |
|---|---|---|
| Operator and engineering workstations on Ethernet, through paired Ethernet switches, to the controllers; controllers (redundant pair, linked to each other) to the I/O rack; field devices hardwired to the I/O | Kemari, Korangi (approved), the two F&G images | The F&G chain: level 2 workstations, level 1 switches and controllers, level 0 devices. Field devices are one icon per type, with no quantities. |
| Devices of a room on one Ethernet bus, two Ethernet switches, each with a fibre patch panel, then a fibre ring | Maaden, KSU (control room, server room) | Switches and patch panels come in pairs. The ring links rooms and buildings. |
| Panel or building blocks hang off the fibre ring; inside each block the devices are chained controller, switch, patch panel | KSU old buildings (2 controllers, 2 switches, 2 patch panels per building), Maaden substations | "Redundant networking is considered for each building": two links. |
| Master control panels hold a redundant controller pair, switches and fibre patch panels, and sit on the ring | KSU overview | North and south master panels. |
| Per well site: redundant CPU, HMI, LTE modem, three I/O racks (simplex process, redundant ESD, redundant F&G), two Ethernet switches; sites reach the central control room by wireless or fibre | Murtiba | 14 identical sites; large and repetitive. |
| Layers drawn top to bottom: enterprise, IT/OT firewall, DMZ (level 3.5), OT firewall, level 3, level 2, communication medium (firewall and gateway), level 1, level 0; a primary and a secondary site side by side; a virtual environment shown as a dashed box with its contents listed in a side panel | WAVE (L3.5 example) | The DMZ is crossed only through firewalls; VM contents are boxes in a note. |

Client rules that are not observations: PLC-to-field control signals are always hardwired (user); the cable colours (client's drawing
instructions); field devices, third-party connectivity and the DMZ are drawn as boxes (client's drawing instructions).

What is **not** known and must not be guessed: which device connects to which in a given project. Unless the
user states a link, the model asks; it is drawn only if the user states it or says to use the usual arrangement (then it is `assumed`).
