"""Default configuration for ack - file type definitions and ignore rules."""

from __future__ import annotations

import ack_grep

_OPTIONS_BLOCK = r"""# This is the default ackrc for ack version {version}.

# There are four different ways to match
#
# is:  Match the filename exactly
#
# ext: Match the extension of the filename exactly
#
# match: Match the filename against a regular expression
#
# firstlinematch: Match the first 250 characters of the first line
#   of text against a regular expression.  This is only for
#   the --type-add option.


### Directories to ignore

# Bazaar
--ignore-directory=is:.bzr

# Codeville
--ignore-directory=is:.cdv

# Interface Builder (Xcode)
--ignore-directory=is:~.dep
--ignore-directory=is:~.dot
--ignore-directory=is:~.nib
--ignore-directory=is:~.plst

# Git
--ignore-directory=is:.git
--ignore-file=is:.git

# Mercurial
--ignore-directory=is:.hg

# Quilt
--ignore-directory=is:.pc

# Subversion
--ignore-directory=is:.svn

# Monotone
--ignore-directory=is:_MTN

# CVS
--ignore-directory=is:CVS

# RCS
--ignore-directory=is:RCS

# SCCS
--ignore-directory=is:SCCS

# darcs
--ignore-directory=is:_darcs

# Vault/Fortress
--ignore-directory=is:_sgbak

# autoconf
--ignore-directory=is:autom4te.cache

# Perl module building
--ignore-directory=is:blib
--ignore-directory=is:_build

# Perl Devel::Cover module's output directory
--ignore-directory=is:cover_db

# Node modules created by npm
--ignore-directory=is:node_modules

# CMake cache
--ignore-directory=is:CMakeFiles

# Eclipse workspace folder
--ignore-directory=is:.metadata

# Cabal (Haskell) sandboxes
--ignore-directory=is:.cabal-sandbox

# Python caches
--ignore-directory=is:__pycache__
--ignore-directory=is:.pytest_cache

# macOS Finder remnants
--ignore-directory=is:__MACOSX
--ignore-file=is:.DS_Store

### Files to ignore

# Backup files
--ignore-file=ext:bak
--ignore-file=match:/~$/

# Emacs swap files
--ignore-file=match:/^#.+#$/

# vi/vim swap files
--ignore-file=match:/[._].*[.]swp$/

# core dumps
--ignore-file=match:/core[.]\d+$/

# minified JavaScript
--ignore-file=match:/[.-]min[.]js$/
--ignore-file=match:/[.]js[.]min$/

# minified CSS
--ignore-file=match:/[.]min[.]css$/
--ignore-file=match:/[.]css[.]min$/

# JS and CSS source maps
--ignore-file=match:/[.]js[.]map$/
--ignore-file=match:/[.]css[.]map$/

# PDFs
--ignore-file=ext:pdf

# Common graphics, just as an optimization
--ignore-file=ext:gif,jpg,jpeg,png

# Common archives, as an optimization
--ignore-file=ext:gz,tar,tgz,zip

# Python compiled modules
--ignore-file=ext:pyc,pyd,pyo

# Python's pickle serialization format
--ignore-file=ext:pkl,pickle

# C extensions
--ignore-file=ext:so

# Compiled gettext files
--ignore-file=ext:mo

# Visual Studio user and workspace settings
--ignore-dir=is:.vscode

### Filetypes defined

# Makefiles
--type-add=make:ext:mk
--type-add=make:ext:mak
--type-add=make:is:makefile
--type-add=make:is:Makefile
--type-add=make:is:Makefile.Debug
--type-add=make:is:Makefile.Release
--type-add=make:is:GNUmakefile

# Rakefiles
--type-add=rake:is:Rakefile

# CMake
--type-add=cmake:is:CMakeLists.txt
--type-add=cmake:ext:cmake

# Bazel build tool
--type-add=bazel:ext:bzl
--type-add=bazel:ext:bazelrc
--type-add=bazel:is:BUILD
--type-add=bazel:is:WORKSPACE

# Actionscript
--type-add=actionscript:ext:as,mxml

# Ada
--type-add=ada:ext:ada,adb,ads

# ASP
--type-add=asp:ext:asp

# ASP.Net
--type-add=aspx:ext:master,ascx,asmx,aspx,svc

# Assembly
--type-add=asm:ext:asm,s

# DOS/Windows batch
--type-add=batch:ext:bat,cmd

# ColdFusion
--type-add=cfmx:ext:cfc,cfm,cfml

# Clojure
--type-add=clojure:ext:clj,cljs,edn,cljc

# C
--type-add=cc:ext:c,h,xs

# C header files
--type-add=hh:ext:h

# CoffeeScript
--type-add=coffeescript:ext:coffee

# C++
--type-add=cpp:ext:cpp,cc,cxx,m,hpp,hh,h,hxx

# C++ header files
--type-add=hpp:ext:hpp,hh,h,hxx

# C#
--type-add=csharp:ext:cs

# Crystal-lang
--type-add=crystal:ext:cr,ecr

# CSS
--type-add=css:ext:css

# Dart
--type-add=dart:ext:dart

# Delphi
--type-add=delphi:ext:pas,int,dfm,nfm,dof,dpk,dproj,groupproj,bdsgroup,bdsproj

# Elixir
--type-add=elixir:ext:ex,exs

# Elm
--type-add=elm:ext:elm

# Emacs Lisp
--type-add=elisp:ext:el

# Erlang
--type-add=erlang:ext:erl,hrl

# Fortran
--type-add=fortran:ext:f,f77,f90,f95,f03,for,ftn,fpp

# Go
--type-add=go:ext:go

# Groovy
--type-add=groovy:ext:groovy,gtmpl,gpp,grunit,gradle

# GSP
--type-add=gsp:ext:gsp

# Haskell
--type-add=haskell:ext:hs,lhs

# HTML
--type-add=html:ext:htm,html,xhtml

# Jade
--type-add=jade:ext:jade

# Java
--type-add=java:ext:java,properties

# JavaScript
--type-add=js:ext:js

# JSP
--type-add=jsp:ext:jsp,jspx,jspf,jhtm,jhtml

# JSON
--type-add=json:ext:json

# Kotlin
--type-add=kotlin:ext:kt,kts

# Less
--type-add=less:ext:less

# Common Lisp
--type-add=lisp:ext:lisp,lsp

# Lua
--type-add=lua:ext:lua
--type-add=lua:firstlinematch:/^#!.*\blua(jit)?/

# Markdown
--type-add=markdown:ext:md,markdown

# Matlab
--type-add=matlab:ext:m

# Objective-C
--type-add=objc:ext:m,h

# Objective-C++
--type-add=objcpp:ext:mm,h

# OCaml
--type-add=ocaml:ext:ml,mli,mll,mly

# Perl
--type-add=perl:ext:pl,pm,pod,t,psgi
--type-add=perl:firstlinematch:/^#!.*\bperl/

# Perl tests
--type-add=perltest:ext:t

# Perl's Plain Old Documentation format, POD
--type-add=pod:ext:pod

# PHP
--type-add=php:ext:php,phpt,php3,php4,php5,phtml
--type-add=php:firstlinematch:/^#!.*\bphp/

# Plone
--type-add=plone:ext:pt,cpt,metadata,cpy,py

# PowerShell
--type-add=powershell:ext:ps1,psm1

# PureScript
--type-add=purescript:ext:purs

# Python
--type-add=python:ext:py
--type-add=python:firstlinematch:/^#!.*\bpython/

# Pytest
--type-add=pytest:match:_test\.py$
--type-add=pytest:match:^test_.*\.py$

# R
--type-add=rr:ext:R,Rmd

# reStructured Text
--type-add=rst:ext:rst

# Ruby
--type-add=ruby:ext:rb,rhtml,rjs,rxml,erb,rake,spec
--type-add=ruby:is:Rakefile
--type-add=ruby:firstlinematch:/^#!.*\bruby/

# Rust
--type-add=rust:ext:rs

# Sass
--type-add=sass:ext:sass,scss

# Scala
--type-add=scala:ext:scala,sbt

# Scheme
--type-add=scheme:ext:scm,ss

# Shell
--type-add=shell:ext:sh,bash,csh,tcsh,ksh,zsh,fish
--type-add=shell:firstlinematch:/^#!.*\b(?:ba|t?c|k|z|fi)?sh\b/

# Smalltalk
--type-add=smalltalk:ext:st

# Smarty
--type-add=smarty:ext:tpl

# SQL
--type-add=sql:ext:sql,ctl

# Stylus
--type-add=stylus:ext:styl

# SVG
--type-add=svg:ext:svg

# Swift
--type-add=swift:ext:swift
--type-add=swift:firstlinematch:/^#!.*\bswift/

# Tcl
--type-add=tcl:ext:tcl,itcl,itk

# Terraform
--type-add=terraform=.tf,.tfvars

# TeX & LaTeX
--type-add=tex:ext:tex,cls,sty

# Template Toolkit (Perl)
--type-add=ttml:ext:tt,tt2,ttml

# TOML
--type-add=toml:ext:toml

# TypeScript
--type-add=ts:ext:ts,tsx

# Visual Basic
--type-add=vb:ext:bas,cls,frm,ctl,vb,resx

# Verilog
--type-add=verilog:ext:v,vh,sv

# VHDL
--type-add=vhdl:ext:vhd,vhdl

# Vim
--type-add=vim:ext:vim

# XML
--type-add=xml:ext:xml,dtd,xsd,xsl,xslt,ent,wsdl
--type-add=xml:firstlinematch:/<[?]xml/

# YAML
--type-add=yaml:ext:yaml,yml
"""


def options() -> list[str]:
    return _OPTIONS_BLOCK.format(version=ack_grep.VERSION).split("\n")


def options_clean() -> list[str]:
    return [line for line in options() if line.strip() and not line.strip().startswith("#")]
