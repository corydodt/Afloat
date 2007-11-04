// import Nevow.Athena
// import DeanEdwards
// import Divmod.Defer

Afloat.Graphs = Nevow.Athena.Widget.subclass('Afloat.Graphs');
Afloat.Graphs.methods( // {{{
    function __init__(self, node, accounts) { // {{{
        Afloat.Graphs.upcall(self, '__init__', node);
        $A(accounts).each(function (account) {
            var acctType = account[0];
            var acctId = account[1];
            var chart1 = new FusionCharts(
                "/static/3p/fusionchartsfree/FCF_Column2D.swf",
                "Money Chart", "600", "250");
            chart1.setDataURL('/app/' + acctId + '.xml');
            var graphNode = $$('.graph-' + acctType)[0];
            graphNode.parentNode.hide()
            chart1.render(graphNode);
        });
        $$('.graph-' + accounts[0][0])[0].parentNode.show();

    } // }}}
); // }}}

Afloat.Graphs.selectGraph = function (accountType) {
    $$(".moneys").each(function (n) { n.hide() });
    $$(".graph-" + accountType)[0].parentNode.show()
}

