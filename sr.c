#include <stdlib.h>
#include <stdio.h>
#include <stdbool.h>
#include "emulator.h"
#include "gbn.h"

/* ******************************************************************
   Go Back N protocol.  Adapted from J.F.Kurose
   ALTERNATING BIT AND GO-BACK-N NETWORK EMULATOR: VERSION 1.2

   Network properties:
   - one way network delay averages five time units (longer if there
   are other messages in the channel for GBN), but can be larger
   - packets can be corrupted (either the header or the data portion)
   or lost, according to user-defined probabilities
   - packets will be delivered in the order in which they were sent
   (although some can be lost).

   Modifications:
   - removed bidirectional GBN code and other code not used by prac.
   - fixed C style to adhere to current programming style
   - added GBN implementation
**********************************************************************/

#define RTT  16.0       /* round trip time.  MUST BE SET TO 16.0 when submitting assignment */
#define WINDOWSIZE 6    /* the maximum number of buffered unacked packet
                          MUST BE SET TO 6 when submitting assignment */
#define SEQSPACE 7      /* the min sequence space for GBN must be at least windowsize + 1 */
#define NOTINUSE (-1)   /* used to fill header fields that are not being used */

/* generic procedure to compute the checksum of a packet.  Used by both sender and receiver
   the simulator will overwrite part of your packet with 'z's.  It will not overwrite your
   original checksum.  This procedure must generate a different checksum to the original if
   the packet is corrupted.
*/
int ComputeChecksum(struct pkt packet)
{
  int checksum = 0;
  int i;

  checksum = packet.seqnum;
  checksum += packet.acknum;
  for ( i=0; i<20; i++ )
    checksum += (int)(packet.payload[i]);

  return checksum;
}

bool IsCorrupted(struct pkt packet)
{
  if (packet.checksum == ComputeChecksum(packet))
    return (false);
  else
    return (true);
}


/********* Sender (A) variables and functions ************/

static struct pkt buffer[WINDOWSIZE];  /* array for storing packets waiting for ACK */
static int windowfirst, windowlast;    /* array indexes of the first/last packet awaiting ACK */
static int windowcount;                /* the number of packets currently awaiting an ACK */
static int A_nextseqnum;               /* the next sequence number to be used by the sender */
static bool acked[SEQSPACE];            // REMEMBER TO WRITE COMMENT 
static float timer_start[SEQSPACE];     // REMEMBER TO WRITE COMMENT 

/* called from layer 5 (application layer), passed the message to be sent to other side */
void A_output(struct msg message)
{
  struct pkt sendpkt;
  int i;

  /* if not blocked waiting on ACK */
  if ( windowcount < WINDOWSIZE) {
    if (TRACE > 1)
      printf("----A: New message arrives, send window is not full, send new messge to layer3!\n");

    /* create packet */
    sendpkt.seqnum = A_nextseqnum;
    sendpkt.acknum = NOTINUSE;
    for ( i=0; i<20 ; i++ )
      sendpkt.payload[i] = message.data[i];
    sendpkt.checksum = ComputeChecksum(sendpkt);

    /* put packet in window buffer */
    /* windowlast will always be 0 for alternating bit; but not for GoBackN */
    windowlast = (windowlast + 1) % WINDOWSIZE;
    buffer[windowlast] = sendpkt;
    windowcount++;

    acked[sendpkt.seqnum] = false; //REMEMBER TO WRITE UR COMMENT

    /* send out packet */
    if (TRACE > 0)
      printf("Sending packet %d to layer 3\n", sendpkt.seqnum);
    tolayer3 (A, sendpkt);

    /* start timer if first packet in window */
    if (windowcount == 1)
      starttimer(A,RTT);

    /* get next sequence number, wrap back to 0 */
    A_nextseqnum = (A_nextseqnum + 1) % SEQSPACE;
  }
  /* if blocked,  window is full */
  else {
    if (TRACE > 0)
      printf("----A: New message arrives, send window is full\n");
    window_full++;
  }
}


/* called from layer 3, when a packet arrives for layer 4
   In this practical this will always be an ACK as B never sends data.
*/
void A_input(struct pkt packet)
{
  if (!IsCorrupted(packet)) {
    if (TRACE > 0)
      printf("----A: Uncorrupted ACK %d received\n", packet.acknum);

    total_ACKs_received++;

    if (!acked[packet.acknum]) {
      acked[packet.acknum] = true;
      new_ACKs++;

      // Slide the window forward if the first packet is now ACKed
      while (windowcount > 0 && acked[buffer[windowfirst].seqnum]) {
        if (TRACE > 0)
          printf("----A: Sliding window. Removing packet %d\n", buffer[windowfirst].seqnum);
        windowfirst = (windowfirst + 1) % WINDOWSIZE;
        windowcount--;
      }

      stoptimer(A);
      if (windowcount > 0)
        starttimer(A, RTT);
    } else {
      if (TRACE > 0)
        printf("----A: Duplicate ACK %d received. Ignored.\n", packet.acknum);
    }
  } else {
    if (TRACE > 0)
      printf("----A: Corrupted ACK received. Ignored.\n");
  }
}

/* called when A's timer goes off */
void A_timerinterrupt(void)
{
  if (TRACE > 0)
  printf("----A: Timer interrupt. Resending unACKed packets.\n");

for (int i = 0; i < WINDOWSIZE; i++) {
  int idx = (windowfirst + i) % WINDOWSIZE;
  struct pkt pkt = buffer[idx];

  if (!acked[pkt.seqnum]) {
    if (TRACE > 0)
      printf("----A: Resending packet %d\n", pkt.seqnum);
    tolayer3(A, pkt);
    packets_resent++;
  }
}

starttimer(A, RTT); // Always restart timer
}



/* the following routine will be called once (only) before any other */
/* entity A routines are called. You can use it to do any initialization */
void A_init(void)
{
  /* initialise A's window, buffer and sequence number */
  A_nextseqnum = 0;  /* A starts with seq num 0, do not change this */
  windowfirst = 0;
  windowlast = -1;   /* windowlast is where the last packet sent is stored.
		     new packets are placed in winlast + 1
		     so initially this is set to -1
		   */
  windowcount = 0;
}



/********* Receiver (B)  variables and procedures ************/

static int expectedseqnum; /* the sequence number expected next by the receiver */
static int B_nextseqnum;   /* the sequence number for the next packets sent by B */
static struct pkt recv_buffer[SEQSPACE];
static bool received[SEQSPACE];

/* called from layer 3, when a packet arrives for layer 4 at B*/
void B_input(struct pkt packet)
{
  struct pkt ackpkt;
  int i;

  if (!IsCorrupted(packet)) {
    int seq = packet.seqnum;

    // Accept packet in receiver window
    if (!received[seq]) {
      received[seq] = true;
      recv_buffer[seq] = packet;
    }

    // Try to deliver in-order packets
    while (received[expectedseqnum]) {
      if (TRACE > 0)
        printf("----B: Delivering packet %d to application\n", expectedseqnum);
      tolayer5(B, recv_buffer[expectedseqnum].payload);
      received[expectedseqnum] = false;
      expectedseqnum = (expectedseqnum + 1) % SEQSPACE;
      packets_received++;
    }

    // Always send ACK for the received packet
    ackpkt.acknum = seq;
  } else {
    if (TRACE > 0)
      printf("----B: Corrupted packet received. Ignoring.\n");

    // Still send ACK for last in-order packet
    ackpkt.acknum = (expectedseqnum == 0) ? SEQSPACE - 1 : expectedseqnum - 1;
  }

  // Build ACK packet
  ackpkt.seqnum = B_nextseqnum;
  B_nextseqnum = (B_nextseqnum + 1) % 2;
  for (i = 0; i < 20; i++)
    ackpkt.payload[i] = '0';
  ackpkt.checksum = ComputeChecksum(ackpkt);

  tolayer3(B, ackpkt);
}
/* the following routine will be called once (only) before any other */
/* entity B routines are called. You can use it to do any initialization */
void B_init(void)
{
  expectedseqnum = 0;
  B_nextseqnum = 1;
  for (int i = 0; i < SEQSPACE; i++)
    received[i] = false;
}

/******************************************************************************
 * The following functions need be completed only for bi-directional messages *
 *****************************************************************************/

/* Note that with simplex transfer from a-to-B, there is no B_output() */
void B_output(struct msg message)
{
}

/* called when B's timer goes off */
void B_timerinterrupt(void)
{
}
