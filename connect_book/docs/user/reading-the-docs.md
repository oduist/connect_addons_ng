# Reading the Documentation

**Connect Book** puts this documentation inside Odoo. Every Connect module
keeps its pages next to its own code, and the Book collects the pages of the
modules that are actually installed on your database — so what you read always
matches what you run. There is nothing to install separately and nothing to
keep in sync by hand.

## Opening a book

Everything sits under the **Connect** top menu, in the **Documentation**
section. The whole **Connect** menu is reserved for people who have a Connect
role, so if you cannot see it at all, ask your administrator to give you one.

- **Connect ▸ Documentation ▸ User Guide** — the everyday guides, for everyone
  who can open Connect. The page you are reading now is one of them.
- **Connect ▸ Documentation ▸ Admin Guide** — setup and configuration, for
  Connect administrators only. The menu is hidden if you are not one.

## Finding your way around

The window has two panes.

On the left is the table of contents: the installed modules in order, each with
its own pages underneath. The first page is opened for you when the window
loads. Click any other line to switch to it.

On the right is the page itself.

!!! tip "The search box filters the contents, not the text"
    Type a few letters in the box above the table of contents and the list
    narrows down. A module whose **name** matches keeps all of its pages;
    otherwise only the **pages** whose title matches stay, and modules left
    with nothing drop out of the list. The match is case-insensitive and can be
    anywhere in the name.

    It does not search inside the text of the pages. To find a word on the page
    you are reading, use your browser's own find — `Ctrl+F` (`Cmd+F` on a
    Mac).

## Following a cross-reference

Pages link to each other — "see
[How the Book Finds Documentation](../admin/book-setup.md)" and the like. Clicking such a link inside the Book jumps straight to that page in the
right-hand pane; it does not open a new browser tab and does not lose your
place in Odoo.

A link that points at a page you are not allowed to read — an administrator
page, when you have no Connect admin role — simply does nothing.

Links that go outside the documentation (to oduist.com, to a provider's
console) open in a new tab as usual.

## Why a page may be missing

The Book only shows what is on your database:

- a module that is **not installed** contributes no pages at all;
- a module that ships **no documentation** does not appear in the list;
- the **Admin Guide** menu is invisible unless you are a Connect administrator.

If a page you expected is not there, that is what to check first — with your
administrator if need be.

## Language

The Book is served in your Odoo language when a translation of a page exists,
and in the original English otherwise. The choice is per page, so a partially
translated module shows the translated pages translated and the rest in
English. Nothing to switch on: change your own language in Odoo and reopen the
Book.
