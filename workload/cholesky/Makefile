GEM5_PATH = /d/hpc/projects/FRI/GEM5/gem5_workspace/gem5/
ISA = riscv
GXX = riscv64-linux-gnu-gcc

SOURCES = $(wildcard *.c)
TARGETS = $(SOURCES:.c=.bin)

all: $(TARGETS)

%.bin: %.c
	$(GXX) -o $@ $< -static -fopenmp -lpthread -I$(GEM5_PATH)/include -L$(GEM5_PATH)/util/m5/build/$(ISA)/out -I$(GEM5_PATH)/util/m5/src -lm5 -lm -DGEM5

clean:
	rm -f $(TARGETS)