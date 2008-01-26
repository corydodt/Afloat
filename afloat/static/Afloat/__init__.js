// import Nevow.Athena
// import Divmod.Defer

Afloat.newSpinner = function (message) { // {{{
    if (message === undefined) message = '';

    var spinner = document.documentElement.select('.theSpinner')[0].cloneNode(true);
    spinner.insert(message);
    spinner.show();

    return spinner;
} // }}}

var LightboxConfig = Class.create({ // {{{
    opacity:0.7,
    fade:true, 
    fadeDuration: 0.7
}); // }}}

Afloat.modalFromNode = function (node) { // {{{
    // copy the content of node into a modal dialog (lightbox)
    var config = new LightboxConfig();
    config.contents = node.innerHTML;

    // kludge .. hide all embedded stuff when showing the modal
    var embeds = document.documentElement.select('embed');
    $A(embeds).each(function (e) { 
        e.setAttribute('_oldVisibility', e.style['visibility']);
        e.style['visibility'] = 'hidden'; 
    });
    
    // restore embedded stuff when closing the modal
    config.afterClose = function () { $A(embeds).each(function(e) {
        e.style['visibility'] = e.readAttribute('_oldVisibility');
        e.removeAttribute('_oldVisibility');
        }
    )};

    var modal = new Control.Modal(null, config);
    modal.open();
    return modal;
} // }}}

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

Afloat.Graphs.selectGraph = function (accountType) { // {{{
    $$(".moneys").each(function (n) { n.hide() });
    $$(".graph-" + accountType)[0].parentNode.show()
} // }}}

var TIPCONFIG = { // {{{
    fixed: true,
    closeButton: false,
    hook: { target: 'bottomRight', tip: 'bottomLeft' },
    className: 'txnTipTip',
    offset: { x:0, y:15 },
    effect: 'appear',
    duration: 0.2
    // hideOn: { element: 'closeButton' }
}; // }}}

Afloat.Summary = Nevow.Athena.Widget.subclass('Afloat.Summary');
Afloat.Summary.methods( // {{{
    function __init__(self, node, accounts) { // {{{
        Afloat.Summary.upcall(self, '__init__', node);
        $A(node.select('.txnTip')).each(function (a) {
            var rel = a.getAttribute('rel');
            var partner = node.select('[rev=' + rel + ']')[0];
            new Tip(a, partner.innerHTML, TIPCONFIG);
        });
        var updateNode = node.select(".debugUpdate"); 
        if (updateNode.length > 0) {
            Event.observe(updateNode[0], 'click',
                function(ev) { self.debugUpdate(ev); }
            );
        }
    }, // }}}

    function debugUpdate(self, event) { // {{{
        event.stopPropagation();
        event.preventDefault();
        self.callRemote("updateNow").addCallback(function (_done) {
            Afloat.modalFromNode(self.node.select('.debugMessage')[0]);
            window.history.go(0);
        });
        var spinner = Afloat.newSpinner("Updating...");
        event.target.replace(spinner);
    } // }}}
); // }}}

Afloat.Scheduler = Nevow.Athena.Widget.subclass('Afloat.Scheduler');
Afloat.Scheduler.methods( // {{{
    function __init__(self, node, accounts) { // {{{
        Afloat.Scheduler.upcall(self, '__init__', node);
        var entryBox = self.nodeById('newItem');
        self._defaultText = 'Enter a new scheduled item';
        entryBox.value = self._defaultText;
        function clearer(ev) {
            ev.target.clear();
            ev.target.removeClassName('gray');
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
        node.select('.schedulerTable .rowControl').each( function (n) {
            Event.observe(n, 'mouseover', function (e) { 
                n.parentNode.addClassName('strike');
            });
            Event.observe(n, 'mouseout', function (e) { 
                n.parentNode.removeClassName('strike');
            });
            Event.observe(n, 'click', function (e) { 
                self.unschedule(e, n);
            });
        });

        // when there are late transactions, display a UI to reschedule them
        var lateNode = self.nodeById('lateTransactions');
        if (lateNode.select('.lateRow').length > 0) {
            var modal = Afloat.modalFromNode(lateNode);

            var modalBox = $('modal_container');
            modalBox.select('.rowControl input').each(function (n) {
                    Event.observe(n, 'click', function (e) {
                        var row = n.parentNode.parentNode;
                        if (n.checked) {
                            row.addClassName('strike');
                        } else {
                            row.removeClassName('strike');
                        }
                    });
            });

            var unscheduleForm = modalBox.select('form')[0];
            Event.observe(unscheduleForm, 'submit', function (e) { self.massUnschedule(e, modal) });
        }
        //
        // FIXME - prevent the user from closing the modal by clicking outside
        // of it
        //
    }, // }}}

    function gotReport(self, report) { // {{{
        alert(report);
    }, // }}}

    function schedule(self, event) { // {{{
        event.stopPropagation();
        event.preventDefault();
        var newItem = self.nodeById('newItem');
        // strip whitespace
        var val = newItem.value.replace(/^\s*(.*?)\s*$/, '$1');
        if (val == '' || val == self._defaultText) {
            return;
        }
        if (! val.substring(0,1).match(/\w/)) {
            alert('Because of bugs in Google Calendar, you must begin your scheduled item with a letter or number.');
            return;
        }

        var d = self.callRemote("schedule", val).addCallback(function (_done) {
            window.history.go(0);
        });

        // install a spinner over the form
        var spinner = Afloat.newSpinner("Creating new item \"" + val + "\"");
        newItem.parentNode.replace(spinner);

        d.addErrback(function (err, origNode) {
            spinner.replace(origNode);
            alert(err);
        }, 
            newItem.parentNode);

        d.addCallback(function (ret) {
            if (ret == 'OK') {
                // reload the page
                window.history.go(0);
            }
        });
        return d;
    }, // }}}

    function massUnschedule(self, event, modalDialog) { // {{{
        event.stopPropagation();
        event.preventDefault();
        var modalBox = $('modal_container');
        var forgets = [];
        var keeps = [];
        modalBox.select('.rowControl input').each(function (n) {
                if (n.checked) {
                    forgets.push(n.name);
                } else {
                    keeps.push(n.name);
                }
        });

        var d = self.callRemote("massUnschedule", forgets, keeps);
        var spinner = Afloat.newSpinner('Rescheduling');
        modalBox.select('form')[0].replace(spinner);

        d.addCallback(function (winfo) {
            modalDialog.close();
            if (winfo) {
                var d = self.addChildWidgetFromWidgetInfo(winfo);
                d.addCallback(function (w) {
                    Afloat.modalFromNode(w.node);
                });
            }
            return null;
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
                return null;
            });
        }
        return d;
    } // }}}
); // }}}

// vim:set foldmethod=marker:
