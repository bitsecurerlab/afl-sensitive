#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <glib.h>

void main()
{

	uint32_t x1 = 0xffffffff;
	uint32_t x2 = 0x7fffffff;
	uint32_t y = 0x11111112;

	uint64_t z1 = ((uint64_t)x1 << 32) + y ;
	printf("x1: 0x%x, y: 0x%x, z: 0x%lx\n", x1, y, z1);

	uint64_t z2 = ((uint64_t)x2 << 32) + y;

	int64_t r = 0x12345678;

	guint h1 = g_int64_hash(&z1);;
	guint h2 = g_int64_hash(&z1);
	printf("h1: 0x%x, h2: 0x%x\n", h1, h2);
}