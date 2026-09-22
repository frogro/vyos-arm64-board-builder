include debian/rules
# Native x86 compilers, ARM64 target; retain Debian's cross-exe wrapper for
# the minority of generated ARM64 helper programs and native Rust macros.
defines := $(filter-out use_thin_lto=true,$(defines)) use_thin_lto=false concurrent_links=1 enable_hevc_parser_and_hw_decoder=true enable_platform_hevc=true
.PHONY: vyarm-cross-gen
vyarm-cross-gen:
	gn gen out/Release --threads=2 --args="$(defines)"
