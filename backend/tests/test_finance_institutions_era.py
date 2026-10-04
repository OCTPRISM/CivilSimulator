"""Era-appropriate finance institutions per civilization genre."""
from app.layer2_civilization.finance_institutions import get_finance_institutions


def test_ancient_no_ming_institutions():
    insts = get_finance_institutions("ancient")
    names = " ".join(i["name"] for i in insts)
    eras = " ".join(i.get("era_label", "") for i in insts)
    assert "山西票号" not in names
    assert "明清" not in eras
    assert "柜坊" in names
    assert any("唐" in i.get("era_label", "") for i in insts)
