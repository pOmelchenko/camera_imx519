# Arducam IMX519 CSI Connector Pinout

Reference based on Arducam's connector documentation and Raspberry Pi's
official camera-connector assignments. The owner's retained product
[photograph](../vendor/module-front-and-back.png) shows **UC-875 Rev.B** and
**15 connector solder contacts**. That is evidence about the pictured board;
the owner's physical board revision and connector have not been inspected.

## Which Connector Applies

| Evidence | What it establishes |
| --- | --- |
| Retained UC-875 Rev.B rear photograph | Fifteen visible solder contacts, consistent with the older 15-pin module. |
| Arducam IMX519 guide, autofocus section | B0371 is listed as `15/Bottom`; the sensor link is described as two-lane CSI-2. |
| Same guide, product catalog | B0371 is listed as `22pin/Top`, contradicting its autofocus section. This discrepancy was still present on 2026-10-11. |
| Arducam generic CSI pinout guide | Standard 15-pin signal assignments also apply to its derived upper-contact connector; contact position changes cable insertion orientation. |

Use the **15-pin table below for the pictured UC-875 Rev.B reference**. The
22-pin column describes the standard RPi host/adapter interface; it does not
identify the pictured camera as a 22-pin module. Count the physical unit's
contacts before selecting a cable. No module-specific UC-875 Rev.B schematic
was located in the reviewed manufacturer references.

## 15-Pin Camera Reference And 22-Pin Host Mapping

The standard 15-pin connector has **1.0 mm pitch**; the standard 22-pin
connector has **0.5 mm pitch**. Arducam's signal names are retained below.
CSI directions are from the camera toward the host. The last column is a
comparison by signal with standard RPi 22-pin numbering, useful when checking
a 15-to-22-pin adapter. It does not qualify a particular cable or Q6A port.

| 15-pin camera contact | Signal | Function at camera | Standard RPi 22-pin contact |
| --- | --- | --- | --- |
| 1 | `GND` | Ground | 1 |
| 2 | `CAM_D0_N` | CSI data lane 0, negative | 2 |
| 3 | `CAM_D0_P` | CSI data lane 0, positive | 3 |
| 4 | `GND` | Ground | 4 |
| 5 | `CAM_D1_N` | CSI data lane 1, negative | 5 |
| 6 | `CAM_D1_P` | CSI data lane 1, positive | 6 |
| 7 | `GND` | Ground | 7 |
| 8 | `CAM_CK_N` | CSI clock, negative | 8 |
| 9 | `CAM_CK_P` | CSI clock, positive | 9 |
| 10 | `GND` | Ground | 10 |
| 11 | `CAM_IO0` | Module-dependent control; generic reference: power enable | 17 |
| 12 | `CAM_IO1` | Module-dependent control; generic reference: LED/clock | 18 |
| 13 | `CAM_SCL` | I2C clock | 20 |
| 14 | `CAM_SDA` | I2C data | 21 |
| 15 | `CAM_3V3` | 3.3 V supply input | 22 |

The remaining standard 22-pin positions are:

| Standard RPi 22-pin contact | Standard signal |
| --- | --- |
| 11 | CSI data lane 2, negative |
| 12 | CSI data lane 2, positive |
| 13 | Ground |
| 14 | CSI data lane 3, negative |
| 15 | CSI data lane 3, positive |
| 16 | Ground |
| 19 | Ground |

A 15-pin camera does not supply lanes 2/3 through a passive adapter. Preserve
the adapter's ground routing; the extra 22-pin ground contacts are not spare
control signals. If the actual camera has 22 contacts, identify its variant
and use a manufacturer-confirmed module assignment before applying this
standard-host reference to it.

The Arducam table calls pin 12 an LED control, while Raspberry Pi describes
both control pins as module-dependent GPIOs. This does **not** establish an
LED, XCLK or external-trigger connection on UC-875 Rev.B. Likewise, 3.3 V
module power does not establish the bare Sony sensor's I/O tolerance. Raspberry
Pi documents 3.3 V host I2C pull-ups; another host needs a compatible interface.

## Pin 1 And Cable Contact Side

Identify pin 1 from board markings or the matching connector drawing. The
standard Raspberry Pi camera-board convention places pin 1 nearest the
observer when the lens faces down and the connector is on the right. This
describes Raspberry Pi camera boards; it is not independent confirmation of
UC-875 Rev.B numbering. A clearly labelled pin-1 marker is not established
by the retained UC-875 photograph.

For the photographed module, confirm the ground end with an unpowered
continuity check to a known ground point, and confirm the 3.3 V end against
board documentation before applying power. Do not infer the power end from
the blue ribbon stiffener or a rotated product photograph.

Cable metal must meet the connector's metal contacts. In a right-angle
connector, an upper contact is on the latch side, away from the PCB; a lower
contact is on the PCB side. Establish that contact position on the actual
connector instead of relying on the conflicting `Top`/`Bottom` catalog
labels. Check the routing and contact side at **both** cable ends. The
[manufacturer connection guide](../vendor/arducam-csi-connection-guide-2026-10-11.html)
is retained as HTML; its externally hosted illustrations are not embedded.

## Sources

- [Original UC-875 Rev.B product photograph](../vendor/module-front-and-back.png),
  supplied on 2026-09-23; [original provenance](../vendor/sources.json).
- Arducam, [Raspberry Pi Camera Pinout](https://docs.arducam.com/Raspberry-Pi-Camera/raspberry-pi-camera-pinout/),
  checked on 2026-10-11; [retained original HTML](../vendor/arducam-csi-pinout-2026-10-11.html).
- Arducam, [16MP IMX519 guide](https://docs.arducam.com/Raspberry-Pi-Camera/Native-camera/16MP-IMX519/),
  checked on 2026-10-11; [retained original HTML](../vendor/arducam-imx519-guide-2026-10-11.html).
- Arducam, [native-camera hardware connection guide](https://docs.arducam.com/Raspberry-Pi-Camera/Native-camera/Quick-Start-Guide/#hardware-setup),
  checked on 2026-10-11; [retained original HTML](../vendor/arducam-csi-connection-guide-2026-10-11.html).
- Raspberry Pi Ltd, [camera connector reference](https://www.raspberrypi.com/documentation/accessories/camera.html#pinout-information),
  checked on 2026-10-11; [retained original AsciiDoc](../vendor/raspberry-pi-camera-advanced-2026-10-11.adoc)
  at documentation commit `62ba0a0c2dd5030fe9b19458fa9bd174a451f79b`, CC BY-SA 4.0.
- [Retrieval, source scope, versions and SHA-256 manifest](../vendor/pinout-sources.json)
  and [checksums](../vendor/SHA256SUMS).

Return to the [IMX519 camera reference](../../README.md).
