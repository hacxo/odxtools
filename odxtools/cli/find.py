# SPDX-License-Identifier: MIT
import argparse
from typing import Dict, List, Optional

from ..database import Database
from ..diagservice import DiagService
from ..exceptions import odxraise
from ..odxtypes import ParameterValue
from ..singleecujob import SingleEcuJob
from . import _parser_utils
from ._print_utils import print_diagnostic_service

# name of the tool
_odxtools_tool_name_ = "find"


def get_display_value(v: ParameterValue) -> str:
    import binascii

    if isinstance(v, bytes):
        return binascii.hexlify(v, " ", 1).decode("utf-8")
    elif isinstance(v, int):
        return f"{v} ({hex(v)})"
    else:
        return str(v)


def print_decoded_message(service: DiagService, message: bytes) -> None:
    decoded = service.decode_message(message)
    print(f"\nDecoded {decoded.coding_object}:")
    for k, v in decoded.param_dict.items():
        print(f"\t{k}: {get_display_value(v)}")


def print_summary(
    odxdb: Database,
    ecu_variants: Optional[List[str]] = None,
    data: Optional[bytes] = None,
    service_names: Optional[List[str]] = None,
    decode: bool = False,
    print_params: bool = False,
    allow_unknown_bit_lengths: bool = False,
) -> None:
    ecu_names = ecu_variants if ecu_variants else [ecu.short_name for ecu in odxdb.ecus]
    services: Dict[DiagService, List[str]] = {}
    for ecu_name in ecu_names:
        ecu = odxdb.ecus[ecu_name]
        if not ecu:
            print(f"The ecu variant '{ecu_name}' could not be found!")
            continue
        if data:
            found_services = ecu._find_services_for_uds(data)
            for found_service in found_services:
                ecu_names = services.get(found_service, [])
                ecu_names.append(ecu_name)
                services[found_service] = ecu_names

        if service_names:
            for service_name_search in service_names:
                for service in ecu.services:
                    if service_name_search.lower() in service.short_name.lower():
                        ecu_names = services.get(service, [])
                        ecu_names.append(ecu_name)
                        services[service] = ecu_names

    for service, ecu_names in services.items():
        display_names = ", ".join(ecu_names)
        filler = str.ljust("", len(display_names), "=")
        print(f"\n{filler}")
        print(f"{', '.join(ecu_names)}")
        print(f"{filler}\n\n")
        if isinstance(service, DiagService):
            print_diagnostic_service(
                service,
                print_params=print_params,
                allow_unknown_bit_lengths=allow_unknown_bit_lengths,
                print_pre_condition_states=True,
                print_state_transitions=True,
                print_audiences=True,
            )
        elif isinstance(service, SingleEcuJob):
            print(f"SingleEcuJob: {service.odx_id}")
        else:
            print(f"Unknown service: {service}")

        if decode:
            if data is None:
                odxraise("data required for decoding")
            print_decoded_message(service, data)


def add_subparser(subparsers: "argparse._SubParsersAction") -> None:
    parser = subparsers.add_parser(
        "find",
        description="\n".join([
            "Find & print services by hex-data, or name, can also decodes requests",
            "",
            "Examples:",
            "  For displaying the service associated with the request 10 01:",
            "    odxtools find ./path/to/database.pdx -d 10 01",
            "  For displaying the service associated with the request 10 01, and decoding it:",
            "    odxtools find ./path/to/database.pdx -D 10 01",
            "  For displaying the services associated with the partial name 'Reset' without details:",
            '    odxtools find ./path/to/database.pdx -s "Reset" --no-details',
            "  For more information use:",
            "    odxtools find -h",
        ]),
        help="Find & print services by hex-data, or name. Can also decode the request.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    _parser_utils.add_pdx_argument(parser)

    parser.add_argument(
        "-v",
        "--variants",
        nargs="+",
        metavar="VARIANT",
        required=False,
        help="Specifies which ecu variants should be included.",
        default="all",
    )

    parser.add_argument(
        "-d",
        "--data",
        nargs="*",
        default=None,
        metavar="DATA",
        required=False,
        help="Print a list of diagnostic services associated with the hex request.",
    )

    parser.add_argument(
        "-D",
        "--decode",
        nargs="*",
        default=None,
        metavar="DECODE",
        required=False,
        help="Print a list of diagnostic services associated with the hex request and decode the request.",
    )

    parser.add_argument(
        "-s",
        "--service-names",
        nargs="*",
        default=None,
        metavar="SERVICES",
        required=False,
        help="Print a list of diagnostic services partially matching given service names",
    )

    parser.add_argument(
        "-nd",
        "--no-details",
        action="store_false",
        required=False,
        help="Don't show all service details",
    )

    parser.add_argument(
        "-ro",
        "--relaxed-output",
        action="store_true",
        required=False,
        help="Relax output formatting rules (allow unknown bitlengths for ascii representation)",
    )


def hex_to_binary(data: str) -> bytes:
    import binascii

    return binascii.unhexlify("".join(data).replace(" ", ""))


def run(args: argparse.Namespace) -> None:
    odxdb = _parser_utils.load_file(args)

    variants = args.variants if args.variants else None

    data = (
        hex_to_binary(args.data)
        if args.data else hex_to_binary(args.decode) if args.decode else None)
    decode = True if args.decode else False

    print_summary(
        odxdb,
        ecu_variants=None if variants == "all" else variants,
        data=data,
        decode=decode,
        service_names=args.service_names,
        print_params=args.no_details,
        allow_unknown_bit_lengths=args.relaxed_output,
    )
