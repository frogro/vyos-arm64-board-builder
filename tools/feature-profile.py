#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path


TRUE_VALUES = {"1", "true", "yes", "y", "on"}
FALSE_VALUES = {"0", "false", "no", "n", "off"}


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValueError(f"invalid boolean value: {value}")


def derive(
    extended_network: bool,
    tailscale_subnet_router: bool,
    kvm_over_ip: bool,
) -> dict:
    enabled = []
    profile_parts = []
    if extended_network:
        enabled.append("extended-network")
        profile_parts.append("network")
    if tailscale_subnet_router:
        enabled.append("tailscale-subnet-router")
        profile_parts.append("tailscale")
    if kvm_over_ip:
        enabled.append("kvm-over-ip")
        profile_parts.append("kvm")

    return {
        "schema": 1,
        "profile": "-".join(profile_parts) if profile_parts else "base",
        "features": {
            "extended_network": extended_network,
            "tailscale_subnet_router": tailscale_subnet_router,
            "kvm_over_ip": kvm_over_ip,
        },
        "enabled_features": enabled,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--extended-network", default="no")
    parser.add_argument("--tailscale-subnet-router", default="no")
    parser.add_argument("--kvm-over-ip", default="no")
    parser.add_argument("--output-env", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    args = parser.parse_args()

    try:
        data = derive(
            parse_bool(args.extended_network),
            parse_bool(args.tailscale_subnet_router),
            parse_bool(args.kvm_over_ip),
        )
    except ValueError as error:
        parser.error(str(error))

    profile = data["profile"]
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", profile):
        parser.error(f"invalid derived profile: {profile}")

    args.output_env.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_env.write_text(
        "\n".join(
            [
                f"BUILD_PROFILE={profile}",
                "EXTENDED_NETWORK=" + ("yes" if data["features"]["extended_network"] else "no"),
                "TAILSCALE_SUBNET_ROUTER=" + ("yes" if data["features"]["tailscale_subnet_router"] else "no"),
                "KVM_OVER_IP=" + ("yes" if data["features"]["kvm_over_ip"] else "no"),
                "",
            ]
        ),
        encoding="utf-8",
    )
    args.output_json.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
