// import Nevow.Athena
// import DeanEdwards
// import Divmod.Defer

Afloat.newSpinner = function (message) {
    if (message === undefined) message = '';

    var spinner = document.documentElement.select('.theSpinner')[0].cloneNode(true);
    spinner.insert(message);
    spinner.show();

    return spinner;
}

Afloat.Graphs = Nevow.Athena.Widget.subclass('Afloat.Graphs');
Afloat.Graphs.methods( // {{{
    function __init__(self, node, accounts) { // {{{
        Afloat.Graphs.upcall(self, '__init__', node);
        $A(accounts).each(function (account) {
            var acctType = account[0];
            var acctId = account[1];
            var chart1 = new FusionCharts(
                "/static/3p/fusionchartsfree/FCF_Column2D.swf",
                "Money Chart", "800", "250");
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

var TIPCONFIG = {
    fixed: true,
    closeButton: false,
    hook: { target: 'bottomRight', tip: 'bottomLeft' },
    className: 'txnTipTip',
    offset: { x:0, y:15 },
    effect: 'appear',
    duration: 0.2
    // hideOn: { element: 'closeButton' }
};

Afloat.Summary = Nevow.Athena.Widget.subclass('Afloat.Summary');
Afloat.Summary.methods( // {{{
    function __init__(self, node, accounts) { // {{{
        Afloat.Summary.upcall(self, '__init__', node);
        $A(node.select('.txnTip')).each(function (a) {
            var rel = a.getAttribute('rel');
            var partner = node.select('[rev=' + rel + ']')[0];
            new Tip(a, partner.innerHTML, TIPCONFIG);
        });
    } // }}}
); // }}}

Afloat.Scheduler = Nevow.Athena.Widget.subclass('Afloat.Scheduler');
Afloat.Scheduler.methods( // {{{
    function __init__(self, node, accounts) { // {{{
        Afloat.Scheduler.upcall(self, '__init__', node);
        var entryBox = self.nodeById('newItem');
        entryBox.value = 'Enter a new scheduled item';
        entryBox.select();
        node.select('.schedulerLeft h3')[0].focus();
        function clearer(ev) {
            ev.target.clear();
            Event.stopObserving(ev.target, 'focus', clearer);
            Event.stopObserving(ev.target, 'click', clearer);
        }
        Event.observe(entryBox, 'focus', clearer);
        Event.observe(entryBox, 'click', clearer);
        var form = document.forms['scheduler'];
        Event.observe(form, 'submit', function (e) { self.schedule(e) });
        var go = self.nodeById('submit');
        Event.observe(go, 'click', function (e) { self.schedule(e) });

        // make the cancel button's hover display strikethrough
        node.select('.cancelButton').each( function (n) {
            Event.observe(n, 'mouseover', function (e) { 
                n.parentNode.addClassName('strike');
            });
            Event.observe(n, 'mouseout', function (e) { 
                n.parentNode.removeClassName('strike');
            });
            Event.observe(n, 'click', function (e) { self.unschedule(e, n) });
        });
    }, // }}}

    function schedule(self, event) { // {{{
        event.stopPropagation();
        event.preventDefault();
        var newItem = self.nodeById('newItem');
        var val = newItem.value;
        var d = self.callRemote("schedule", val);

        // install a spinner over the form
        var spinner = Afloat.newSpinner("Creating new item \"" + val + "\"");
        newItem.parentNode.replace(spinner);

        d.addCallback(function (ret) {
            if (ret == 'OK') {
                // reload the page
                window.history.go(0);
            }
        });
        return d;
    }, // }}}

    function unschedule(self, event, target) { // {{{
        var n = target;
        var p = n.parentNode;
        var memo = p.select('.memo')[0].innerHTML;
        if (confirm("Un-schedule \"" + memo + "\"?")) { 
            var d = self.callRemote("unschedule", n.getAttribute('rev'));
            var spinner = Afloat.newSpinner();
            n.replace(spinner);
            d.addCallback(function (ret) {
                if (ret == 'OK') {
                    // reload the page
                    window.history.go(0);
                }
            });
        }
        return d;
    } // }}}
); // }}}
