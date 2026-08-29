from app.modules.streaming.api.router import _build_ice_servers


def test_build_ice_servers_use_production_fallback():
    servers = _build_ice_servers()

    assert len(servers) == 3
    assert servers[0].urls == [
        "stun:stream.paku.com.pe:5349",
        "stun:stream.paku.com.pe:3478",
    ]
    assert servers[1].urls == ["turns:stream.paku.com.pe:5349"]
    assert servers[1].username == "pakuuser"
    assert servers[1].credential == "pakupassword"
    assert servers[2].urls == ["turn:stream.paku.com.pe:3478"]
    assert servers[2].username == "pakuuser"
    assert servers[2].credential == "pakupassword"
