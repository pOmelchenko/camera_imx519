CXX ?= g++
CXXFLAGS ?= -std=c++17 -O3 -Wall -Wextra -Werror -pthread
KERNEL ?= $(shell uname -r)
BASE_DTB ?= build/base-q6a.dtb
DEMO_LIBS = $(shell pkg-config --cflags --libs libcamera sdl2 glesv2)
OVERLAYS = $(addprefix build/imx519-cam,$(addsuffix .dtbo,1 2 3))

.PHONY: demo driver overlay overlay-check check fetch install-overlays-disabled
demo: build/imx519-demo

build/imx519-demo: demo/imx519-demo.cpp
	mkdir -p build
	$(CXX) $(CXXFLAGS) $< -o $@.new $(DEMO_LIBS)
	mv $@.new $@

fetch:
	python3 tools/fetch-driver.py

driver: fetch
	mkdir -p build/driver
	cp vendor/imx519.c vendor/ak7375.c build/driver/
	patch --batch --forward -d build/driver -p1 < patches/imx519-linux-7.patch
	printf 'obj-m += imx519.o ak7375.o\nccflags-y += -Werror\n' > build/driver/Kbuild
	$(MAKE) -C /lib/modules/$(KERNEL)/build M=$(CURDIR)/build/driver -j4 modules

overlay: $(OVERLAYS)

build/imx519-cam%.dtbo: overlay/imx519-cam%.dts
	mkdir -p build
	dtc -@ -I dts -O dtb -o $@ $<

overlay-check: overlay
	python3 tools/check-overlays.py --base $(BASE_DTB) --build-dir build

check: demo
	./build/imx519-demo --self-test

install-overlays-disabled: overlay
	python3 tools/install-overlays-disabled.py --kernel $(KERNEL)
