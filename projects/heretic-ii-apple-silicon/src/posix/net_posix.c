#include "qcommon.h"
#include "Random.h"

#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <netdb.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

#define MAX_LOOPBACK 4
#define NUM_SOCKETS 3

typedef struct
{
	byte data[MAX_MSGLEN];
	int datalen;
} loopmsg_t;

typedef struct
{
	loopmsg_t msgs[MAX_LOOPBACK];
	int get;
	int send;
} loopback_t;

static loopback_t loopbacks[NUM_SOCKETS];
static int ip_sockets[NUM_SOCKETS] = { -1, -1, -1 };
static cvar_t* net_shownet;
static cvar_t* noudp;

static void NetadrToSockadr(const netadr_t* a, struct sockaddr_in* s)
{
	memset(s, 0, sizeof(*s));
	s->sin_family = AF_INET;
	s->sin_port = a->port;
	if (a->type == NA_BROADCAST)
		s->sin_addr.s_addr = INADDR_BROADCAST;
	else if (a->type == NA_IP)
		memcpy(&s->sin_addr.s_addr, a->ip, 4);
}

static void SockadrToNetadr(const struct sockaddr_in* s, netadr_t* a)
{
	a->type = NA_IP;
	memcpy(a->ip, &s->sin_addr.s_addr, 4);
	a->port = s->sin_port;
}

qboolean NET_CompareAdr(const netadr_t* a, const netadr_t* b)
{
	if (a->type != b->type)
		return false;
	if (a->type == NA_LOOPBACK)
		return true;
	if (a->type == NA_IP)
		return a->port == b->port && memcmp(a->ip, b->ip, 4) == 0;
	return false;
}

qboolean NET_CompareBaseAdr(const netadr_t* a, const netadr_t* b)
{
	if (a->type != b->type)
		return false;
	if (a->type == NA_LOOPBACK)
		return true;
	if (a->type == NA_IP)
		return memcmp(a->ip, b->ip, 4) == 0;
	return false;
}

char* NET_AdrToString(const netadr_t* a)
{
	static char s[64];
	if (a->type == NA_LOOPBACK)
		snprintf(s, sizeof(s), "loopback");
	else if (a->type == NA_IP)
		snprintf(s, sizeof(s), "%u.%u.%u.%u:%u", a->ip[0], a->ip[1], a->ip[2], a->ip[3], ntohs(a->port));
	else
		snprintf(s, sizeof(s), "unknown");
	return s;
}

qboolean NET_StringToAdr(const char* s, netadr_t* a)
{
	if (strcmp(s, "localhost") == 0 || strcmp(s, "loopback") == 0)
	{
		memset(a, 0, sizeof(*a));
		a->type = NA_LOOPBACK;
		return true;
	}

	char copy[128];
	snprintf(copy, sizeof(copy), "%s", s);
	char* port = strchr(copy, ':');
	if (port != NULL)
		*port++ = '\0';

	struct hostent* h = gethostbyname(copy);
	if (h == NULL)
		return false;

	memset(a, 0, sizeof(*a));
	a->type = NA_IP;
	memcpy(a->ip, h->h_addr_list[0], 4);
	a->port = port != NULL ? htons((unsigned short)atoi(port)) : 0;
	return true;
}

qboolean NET_IsLocalAddress(const netadr_t* adr)
{
	return adr->type == NA_LOOPBACK;
}

static qboolean NET_GetLoopPacket(const netsrc_t sock, netadr_t* net_from, sizebuf_t* net_message)
{
	loopback_t* loop = &loopbacks[sock];
	if (loop->send - loop->get > MAX_LOOPBACK)
		loop->get = loop->send - MAX_LOOPBACK;
	if (loop->get >= loop->send)
		return false;

	const int i = loop->get & (MAX_LOOPBACK - 1);
	loop->get++;

	memcpy(net_message->data, loop->msgs[i].data, loop->msgs[i].datalen);
	net_message->cursize = loop->msgs[i].datalen;
	memset(net_from, 0, sizeof(*net_from));
	net_from->type = NA_LOOPBACK;
	return true;
}

static void NET_SendLoopPacket(const netsrc_t sock, const int length, const void* data)
{
	loopback_t* loop = &loopbacks[sock ^ 1];
	const int i = loop->send & (MAX_LOOPBACK - 1);
	loop->send++;
	memcpy(loop->msgs[i].data, data, length);
	loop->msgs[i].datalen = length;
}

qboolean NET_GetPacket(const netsrc_t sock, netadr_t* net_from, sizebuf_t* net_message)
{
	if (NET_GetLoopPacket(sock, net_from, net_message))
		return true;

	const int fd = ip_sockets[sock];
	if (fd < 0)
		return false;

	struct sockaddr_in from;
	socklen_t fromlen = sizeof(from);
	const ssize_t ret = recvfrom(fd, net_message->data, net_message->maxsize, 0, (struct sockaddr*)&from, &fromlen);
	if (ret < 0)
		return false;

	net_message->cursize = (int)ret;
	SockadrToNetadr(&from, net_from);
	return true;
}

void NET_SendPacket(const netsrc_t sock, const int length, const void* data, const netadr_t* to)
{
	if (to->type == NA_LOOPBACK)
	{
		NET_SendLoopPacket(sock, length, data);
		return;
	}
	if (to->type != NA_IP && to->type != NA_BROADCAST)
		return;

	const int fd = ip_sockets[sock];
	if (fd < 0)
		return;

	struct sockaddr_in addr;
	NetadrToSockadr(to, &addr);
	sendto(fd, data, length, 0, (struct sockaddr*)&addr, sizeof(addr));
}

static int UDP_OpenSocket(int port)
{
	int fd = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
	if (fd < 0)
		return -1;

	int val = 1;
	setsockopt(fd, SOL_SOCKET, SO_BROADCAST, &val, sizeof(val));
	fcntl(fd, F_SETFL, O_NONBLOCK);

	struct sockaddr_in address;
	memset(&address, 0, sizeof(address));
	address.sin_family = AF_INET;
	address.sin_addr.s_addr = INADDR_ANY;
	address.sin_port = htons((unsigned short)port);
	if (bind(fd, (struct sockaddr*)&address, sizeof(address)) < 0)
	{
		close(fd);
		return -1;
	}

	return fd;
}

void NET_Config(qboolean multiplayer)
{
	(void)multiplayer;
}

void NET_Init(void)
{
	net_shownet = Cvar_Get("net_shownet", "0", 0);
	noudp = Cvar_Get("noudp", "0", CVAR_NOSET);
	if ((int)noudp->value)
		return;
	ip_sockets[NS_CLIENT] = UDP_OpenSocket(PORT_CLIENT);
	ip_sockets[NS_SERVER] = UDP_OpenSocket(PORT_SERVER);
}

void NET_Shutdown(void)
{
	for (int i = 0; i < NUM_SOCKETS; i++)
	{
		if (ip_sockets[i] >= 0)
		{
			close(ip_sockets[i]);
			ip_sockets[i] = -1;
		}
	}
}

void NET_Sleep(int msec)
{
	usleep(msec * 1000);
}
