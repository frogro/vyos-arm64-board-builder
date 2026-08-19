#!/usr/bin/env python3

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent


class EarlyOfDeclarationTests(unittest.TestCase):
    def test_common_early_of_registration_families_are_indexed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            kernel = work / "linux"
            source_dir = kernel / "drivers" / "test"
            source_dir.mkdir(parents=True)

            (source_dir / "early.c").write_text(
                """
                TIMER_OF_DECLARE(timer, "vendor,timer", timer_init);
                CLK_OF_DECLARE_DRIVER(clock, "vendor,clock", clock_init);
                IOMMU_OF_DECLARE(iommu, "vendor,iommu", iommu_init);
                RESERVEDMEM_OF_DECLARE(memory, "vendor,memory", memory_init);
                """,
                encoding="utf-8",
            )

            output = work / "early.tsv"

            subprocess.run(
                [
                    "python3",
                    str(
                        ROOT /
                        "tools" /
                        "linux_early_of_declarations.py"
                    ),
                    "--kernel",
                    str(kernel),
                    "--output",
                    str(output),
                ],
                check=True,
            )

            self.assertEqual(
                set(output.read_text(encoding="utf-8").splitlines()),
                {
                    (
                        "vendor,clock\tdrivers/test/early.c\t"
                        "CLK_OF_DECLARE_DRIVER"
                    ),
                    (
                        "vendor,iommu\tdrivers/test/early.c\t"
                        "IOMMU_OF_DECLARE"
                    ),
                    (
                        "vendor,memory\tdrivers/test/early.c\t"
                        "RESERVEDMEM_OF_DECLARE"
                    ),
                    (
                        "vendor,timer\tdrivers/test/early.c\t"
                        "TIMER_OF_DECLARE"
                    ),
                },
            )

    def test_gic_v2_and_v3_declarations_resolve_to_kbuild_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            work = Path(temporary)
            kernel = work / "linux"
            irqchip = kernel / "drivers" / "irqchip"
            sound = kernel / "sound"

            irqchip.mkdir(parents=True)
            sound.mkdir(parents=True)

            (irqchip / "irq-gic.c").write_text(
                """
                IRQCHIP_DECLARE(
                    gic_400,
                    "arm,gic-400",
                    gic_of_init
                );
                """,
                encoding="utf-8",
            )

            (irqchip / "irq-gic-v3.c").write_text(
                """
                IRQCHIP_DECLARE(
                    gic_v3,
                    "arm,gic-v3",
                    gic_of_init
                );
                """,
                encoding="utf-8",
            )

            (irqchip / "Makefile").write_text(
                (
                    "obj-$(CONFIG_ARM_GIC) += irq-gic.o\n"
                    "obj-$(CONFIG_ARM_GIC_V3) += irq-gic-v3.o\n"
                ),
                encoding="utf-8",
            )

            compatibles = work / "compatibles.txt"
            compatibles.write_text(
                "arm,gic-400\narm,gic-v3\n",
                encoding="utf-8",
            )

            candidates = work / "candidates.config"
            candidates.write_text(
                "CONFIG_ARM_GIC=y\nCONFIG_ARM_GIC_V3=y\n",
                encoding="utf-8",
            )

            mapping = work / "mapping"

            subprocess.run(
                [
                    str(ROOT / "tools" / "map-dtb-of-drivers.sh"),
                    str(kernel),
                    str(compatibles),
                    str(candidates),
                    str(mapping),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            self.assertEqual(
                set((
                    mapping /
                    "compatible-config-map.tsv"
                ).read_text(encoding="utf-8").splitlines()),
                {
                    "arm,gic-400\tCONFIG_ARM_GIC\t"
                    "drivers/irqchip/irq-gic.c",
                    "arm,gic-v3\tCONFIG_ARM_GIC_V3\t"
                    "drivers/irqchip/irq-gic-v3.c",
                },
            )

            graph = work / "graph.json"
            graph.write_text(
                json.dumps(
                    {
                        "nodes": {
                            "/interrupt-controller@0": {
                                "compatible": ["arm,gic-400"],
                            },
                            "/interrupt-controller@1": {
                                "compatible": ["arm,gic-v3"],
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            closure = work / "closure.json"
            closure.write_text(
                json.dumps(
                    {
                        "nodes": {
                            "/interrupt-controller@0": {},
                            "/interrupt-controller@1": {},
                        }
                    }
                ),
                encoding="utf-8",
            )

            context = work / "context"

            subprocess.run(
                [
                    "python3",
                    str(ROOT / "tools" / "dtb-driver-context.py"),
                    "--kernel",
                    str(kernel),
                    "--graph",
                    str(graph),
                    "--closure",
                    str(closure),
                    "--driver-map",
                    str(
                        mapping /
                        "compatible-config-map.tsv"
                    ),
                    "--output-dir",
                    str(context),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            result = json.loads(
                (
                    context /
                    "driver-context.json"
                ).read_text(encoding="utf-8")
            )

            self.assertEqual(
                result["unresolved_count"],
                0,
            )

            resolved = {
                item["path"]: item
                for item in result["resolved"]
            }

            self.assertEqual(
                resolved[
                    "/interrupt-controller@0"
                ]["selected"]["config"],
                "CONFIG_ARM_GIC",
            )

            self.assertEqual(
                resolved[
                    "/interrupt-controller@1"
                ]["selected"]["config"],
                "CONFIG_ARM_GIC_V3",
            )

            for item in resolved.values():
                self.assertTrue(
                    item["selected"]["of_driver_bound"]
                )

                self.assertEqual(
                    item["candidate_filter"],
                    "driver-bound",
                )


if __name__ == "__main__":
    unittest.main()
