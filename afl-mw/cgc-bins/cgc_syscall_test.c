#include <libcgc.h>

char lut[] = "0123456789ABCDEF";

void display_hex(char input)
{
	// char lut[ ] = "0123456789";
	int i;
	char buf[2];
	buf[0] = lut[input >> 4];
	buf[1] = lut[input & 15];
	transmit(STDOUT, buf, 2, NULL);
	
}

void newline()
{
	transmit(STDOUT, "\n", 1, NULL);
}

void transmit_test()
{
	char buf[] = "1234\n";
	size_t n;
	char c;
	int ret = transmit(STDOUT, buf, sizeof(buf)-1, &n);
	c = n + 0x30;
	if(ret == 0)
		transmit(STDOUT, &c, 1, NULL);
	transmit(STDOUT, "\n", 1, NULL);
}

void receive_test()
{
	char buf[100];
	size_t n;
	// transmit(STDOUT, ,)
	int ret = receive(STDIN, buf, 5000, &n);
	//buf[n] = '\n';
	char c = n + 0x30;
	if(ret == 0)
		transmit(STDOUT, &c, 1, NULL);
	transmit(STDOUT, buf, n, NULL);
}

void random_test()
{
	char buf[100];
	size_t n;
	int ret = random(buf, 6, &n);
	if(ret == 0)
	{
		int i;
		for(i = 0; i<n; i++)
		{
			display_hex(buf[i]);
		}
	}
}

void allocate_and_de_test()
{
	int size = 10;
	void* buf;
	int ret = allocate(size, 1, &buf);
	int i;
	if(ret == 0)
	{
		for(i=0;i<size;i++)
		{
			*((char*)buf + i)= i + 0x30;
		}
		for(i=0;i<size;i++)
		{
			transmit(STDOUT, (char *)buf+i, 1, NULL);
		}
		deallocate(buf, size);
	}

	return;
}

void fdwait_test()
{
	// int nfds = STDOUT + 1;
	return;
}

void exec_stack()
{
	return;
}

int main()
{
	// transmit_test();
	// newline();
	receive_test();
	newline();
	// random_test();
	// newline();
	// allocate_test();
	// newline();
	// fdwait_test();
	// _terminate();
	return 0;
}