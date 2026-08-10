
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# This account's XMPP identity (matches PLAYER_ID in rest_server). The client knows
# itself as prod-100001; binding it as anything else makes the "communication service"
# reconnect in a loop. We also adopt the client's self-declared from= JID at runtime.
XMPP_USER = "prod-100001"
XMPP_DOMAIN = "xmpp.prod.ww3.fxtools.gl"

def extract_from_jid(text):
    for q in ("'", '"'):
        tag = f"from={q}"
        if tag in text:
            try:
                jid = text.split(tag, 1)[1].split(q, 1)[0]
                if jid.startswith("prod-") and "@" in jid:
                    return jid
            except Exception:
                pass
    return None

async def send_periodic_pings(writer, client_jid):
    try:
        while True:
            await asyncio.sleep(10)
            keepalive = (
                f"<presence from='xmpp.prod.ww3.fxtools.gl' to='{client_jid}'>"
                "<type>available</type>"
                "</presence>"
            )
            writer.write(keepalive.encode('utf-8'))
            await writer.drain()
            logging.info("[>] Sent server presence keepalive")
    except asyncio.CancelledError:
        pass
    except Exception:
        pass

async def handle_xmpp(reader, writer):
    addr = writer.get_extra_info('peername')
    logging.info(f"[+] Client connected from {addr}")
    
    keepalive_task = None
    client_jid = f"{XMPP_USER}@{XMPP_DOMAIN}/V2"
    
    try:
        initial_response = (
            "<?xml version='1.0' encoding='UTF-8'?>"
            "<stream:stream xmlns:stream='http://etherx.jabber.org/streams' "
            "xmlns='jabber:client' id='auth-stream-123' version='1.0' xml:lang='en'>"
        )
        writer.write(initial_response.encode('utf-8'))
        await writer.drain()

        features = (
            "<stream:features>"
            "<mechanisms xmlns='urn:ietf:params:xml:ns:xmpp-sasl'>"
            "<mechanism>DIGEST-MD5</mechanism>"
            "<mechanism>PLAIN</mechanism>"
            "</mechanisms>"
            "<register xmlns='http://jabber.org/features/iq-register'/>"
            "</stream:features>"
        )
        writer.write(features.encode('utf-8'))
        await writer.drain()

        while True:
            data = await reader.read(4096)
            if not data:
                break
                
            text_data = data.decode('utf-8', errors='ignore')
            
            if "</stream:stream>" in text_data:
                logging.info("[>] Client requested stream end.")
                writer.write(b"</stream:stream>")
                await writer.drain()
                break

            logging.info(f"[<] FULL TEXT RECEIVED:\n{text_data}")

            # adopt whatever full JID the client declares for itself (authoritative)
            declared = extract_from_jid(text_data)
            if declared:
                client_jid = declared

            if "<auth" in text_data:
                success_response = "<success xmlns='urn:ietf:params:xml:ns:xmpp-sasl'/>"
                writer.write(success_response.encode('utf-8'))
                await writer.drain()
                
                stream_restart = (
                    "<?xml version='1.0' encoding='UTF-8'?>"
                    "<stream:stream xmlns:stream='http://etherx.jabber.org/streams' "
                    "xmlns='jabber:client' id='auth-stream-123' version='1.0' xml:lang='en'>"
                    "<stream:features>"
                    "<bind xmlns='urn:ietf:params:xml:ns:xmpp-bind'/>"
                    "<session xmlns='urn:ietf:params:xml:ns:xmpp-session'/>"
                    "</stream:features>"
                )
                writer.write(stream_restart.encode('utf-8'))
                await writer.drain()
                logging.info("[>] Sent SASL success and restarted stream features.")

            elif "<bind" in text_data:
                resource_str = "V2"
                if "<resource>" in text_data and "</resource>" in text_data:
                    try:
                        resource_str = text_data.split("<resource>")[1].split("</resource>")[0]
                    except:
                        pass
                
                client_jid = f"{XMPP_USER}@{XMPP_DOMAIN}/{resource_str}"

                bound_response = (
                    "<iq type='result' id='_xmpp_bind1'>"
                    "<bind xmlns='urn:ietf:params:xml:ns:xmpp-bind'>"
                    f"<jid>{client_jid}</jid>"
                    "</bind>"
                    "</iq>"
                )
                writer.write(bound_response.encode('utf-8'))
                await writer.drain()
                logging.info(f"[>] Sent JID bind success with JID: {client_jid}")

            elif "<session" in text_data:
                session_response = "<iq type='result' id='_xmpp_session1'/>"
                writer.write(session_response.encode('utf-8'))
                await writer.drain()
                
                # Шлем полный набор начальных IQ-пакетов, чтобы клиент не падал в таймаут
                init_packs = [
                    "<iq type='result' id='roster_1'><query xmlns='jabber:iq:roster'/></iq>",
                    "<iq type='result' id='disco_1'><query xmlns='http://jabber.org/protocol/disco#info'><identity category='server' name='WW3'/></query></iq>",
                    f"<presence from='xmpp.prod.ww3.fxtools.gl' to='{client_jid}'><type>available</type><status>Online</status></presence>"
                ]
                for pack in init_packs:
                    writer.write(pack.encode('utf-8'))
                    await writer.drain()
                
                if keepalive_task is None:
                    keepalive_task = asyncio.create_task(send_periodic_pings(writer, client_jid))

                logging.info("[>] Sent full extended session initialization pack.")

            elif "<presence" in text_data:
                corr_id = ""
                if "corr-id='" in text_data:
                    try: corr_id = text_data.split("corr-id='")[1].split("'")[0]
                    except: pass
                elif 'corr-id="' in text_data:
                    try: corr_id = text_data.split('corr-id="')[1].split('"')[0]
                    except: pass

                presence_ack = f"<presence from='xmpp.prod.ww3.fxtools.gl' to='{client_jid}' corr-id='{corr_id}'><type>available</type></presence>"
                writer.write(presence_ack.encode('utf-8'))
                await writer.drain()
                logging.info(f"[>] Acknowledged presence with corr-id={corr_id}")

            elif "<ping" in text_data or "urn:xmpp:ping" in text_data:
                ping_id = "unknown"
                if "id='" in text_data:
                    try: ping_id = text_data.split("id='")[1].split("'")[0]
                    except: pass
                elif 'id="' in text_data:
                    try: ping_id = text_data.split('id="')[1].split('"')[0]
                    except: pass
                
                pong_response = f"<iq type='result' id='{ping_id}' from='{XMPP_DOMAIN}' to='{client_jid}'/>"
                writer.write(pong_response.encode('utf-8'))
                await writer.drain()
                logging.info(f"[>] Responded to ping id={ping_id}")

            elif "<iq" in text_data:
                iq_id = "iq_res"
                if "id='" in text_data:
                    try: iq_id = text_data.split("id='")[1].split("'")[0]
                    except: pass
                elif 'id="' in text_data:
                    try: iq_id = text_data.split('id="')[1].split('"')[0]
                    except: pass
                
                iq_response = f"<iq type='result' id='{iq_id}' from='{XMPP_DOMAIN}' to='{client_jid}'/>"
                writer.write(iq_response.encode('utf-8'))
                await writer.drain()
                logging.info(f"[>] Responded universally to IQ id={iq_id}")

    except Exception as e:
        logging.error(f"[-] XMPP error: {e}")
    finally:
        if keepalive_task:
            keepalive_task.cancel()
        writer.close()
        logging.info("[-] Connection closed.")

async def main():
    server_5222 = await asyncio.start_server(handle_xmpp, "127.0.0.1", 5222)
    logging.info("[*] Fixed Stub XMPP server running on 127.0.0.1:5222")

    async with server_5222:
        await server_5222.serve_forever()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Stubs stopped.")
        