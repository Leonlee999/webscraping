from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.core.serializers import serialize
from .models import Applied,Saved
import requests
from django.core.mail import send_mail
from bs4 import BeautifulSoup
from account.models import User
from jobapp.forms import *
from jobapp.models import *
from jobapp.permission import *
User = get_user_model()

titles  =[]
links = []
companies = []
summaries  = []

dates =[]

def job_data(job,location,jt):
    job = job.strip()
    j = job.title().strip()
    items = j.split(' ')
    location = location.strip()
    job = job.replace(' ', '+')

    url = 'https://www.indeed.co.in/jobs?q=' + job + '&l=' + location + '&sort=date' + '&jt='+jt
    res = requests.get(url).content
    soup = BeautifulSoup(res, 'html.parser')
    data = soup.find_all('a', class_='tapItem')
    lst = []
    jobtype = {'fulltime':'1','parttime':'2','internship':'3'}

    for i in data:
        rs = {}
        title = i.find('h2', class_='jobTitle').text.split('new')[1]
        company = i.find('span', class_='companyName').text
        location = i.find('div', class_='companyLocation').text
        href = i['href']
        data_jk = i['data-jk']
        data_tk = i['data-mobtk']
        try:
            salary = i.find('div', class_='salary-snippet').text
        except:
            salary = 'Market Standards'
        rs.update({'title': title, 'company': company, 'location': location,
                   'href': href, 'data_jk': data_jk, 'data_tk': data_tk,'job_type':jobtype[jt] if jt!='' else '','salary':salary})
        lst.append(rs.copy())

    return lst

def home_view(request):

    published_jobs = Job.objects.filter(is_published=True).order_by('-timestamp')
    jobs = published_jobs.filter(is_closed=False)
    lst = job_data('python developer', 'bangalore', 'fulltime')
    lst1 = list(published_jobs.values())
    lst=lst+lst1
    total_candidates = User.objects.filter(role='employee').count()
    total_companies = User.objects.filter(role='employer').count()
    paginator = Paginator(lst, 5)
    page_number = request.GET.get('page',None)
    page_obj = paginator.get_page(page_number)


    if request.is_ajax():
        print(page_obj.object_list)
        next_page_number = None
        if page_obj.has_next():
            next_page_number = page_obj.next_page_number()

        prev_page_number = None       
        if page_obj.has_previous():
            prev_page_number = page_obj.previous_page_number()

        data={
            'job_lists':page_obj.object_list,
            'current_page_no':page_obj.number,
            'next_page_number':next_page_number,
            'no_of_page':paginator.num_pages,
            'prev_page_number':prev_page_number
        }    
        return JsonResponse(data,safe=False)
    
    context = {

    'total_candidates': total_candidates,
    'total_companies': total_companies,
    'total_jobs': len(lst),
    'total_completed_jobs':len(published_jobs.filter(is_closed=True)),
    'page_obj': page_obj
    }
    print('ok')
    return render(request, 'jobapp/index.html', context)


def job_list_View(request):
    """

    """
    job_list = Job.objects.filter(is_published=True,is_closed=False).order_by('-timestamp')
    paginator = Paginator(job_list, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {

        'page_obj': page_obj,

    }
    return render(request, 'jobapp/job-list.html', context)


@login_required(login_url=reverse_lazy('account:login'))
@user_is_employer
def create_job_View(request):
    """
    Provide the ability to create job post
    """
    form = JobForm(request.POST or None)

    user = get_object_or_404(User, id=request.user.id)
    categories = Category.objects.all()

    if request.method == 'POST':

        if form.is_valid():

            instance = form.save(commit=False)
            instance.user = user
            instance.save()
            # for save tags
            form.save_m2m()
            messages.success(
                    request, 'You are successfully posted your job! Please wait for review.')
            return redirect(reverse("jobapp:single-job", kwargs={
                                    'id': instance.id
                                    }))

    context = {
        'form': form,
        'categories': categories
    }
    return render(request, 'jobapp/post-job.html', context)


def single_job_view(request):
    """
    Provide the ability to view job details
    """
    tk = request.GET.get('tk')
    jk = request.GET.get('jk')
    title = request.GET.get('title')
    company = request.GET.get('company')
    location = request.GET.get('location')
    job_type = request.GET.get('job_type')
    salary = request.GET.get('salary')
    href = request.GET.get('href')
    url = 'https://in.indeed.com/viewjob?jk='+jk+'&from=tp-serp&tk='+tk
    res = requests.get(url).content
    soup = BeautifulSoup(res, 'html.parser')
    data = soup.find('div', class_='jobsearch-jobDescriptionText')

    saved_lst = []
    applied_list = []
    for i in Saved.objects.all():
        saved_lst.append(i.title)
    for j in Applied.objects.all():
        applied_list.append(j.title)

    rs={}

    rs.update({'title': title, 'company': company, 'location': location,'description':data.text if data!=None else 'No description, Company removed this Job Thank you .','href':href,'job_type':job_type,'salary':salary})
    context = {
        'job': rs,
        'saved':True if title in saved_lst else False,
        'applied':True if title in applied_list else False

    }
    if request.method=='POST':
        title = request.POST.get('title')
        company = request.POST.get('company')
        location = request.POST.get('location')
        href = request.POST.get('href')
        save1 = request.POST.get('save')
        href = 'https://in.indeed.com' + href
        user = get_object_or_404(User, id=request.user.id)

        if save1 == '1':
            saved = Saved.objects.create(user=user,title=title, company=company, location=location, url=href, applied=False)
            saved.save()
            return redirect('/dashboard/')
        else:
            send_mail('Careers djblock','Congratulations on applying to the role {} - {}.'.format(title,company),request.user.email,[request.user.email],fail_silently=False)
            apply = Applied.objects.create(user=user,title=title,company=company,location=location,url=href,applied=True)
            apply.save()
        return redirect(href)
    return render(request, 'jobapp/job-single.html', context)


def search_result_view(request):
    """
        User can search job with multiple fields

    """

    job_list = Job.objects.order_by('-timestamp')

    # Keywords
    if 'job_title_or_company_name' in request.GET:
        job_title_or_company_name = request.GET['job_title_or_company_name']

        if job_title_or_company_name:
            job_list = job_list.filter(title__icontains=job_title_or_company_name) | job_list.filter(
                company_name__icontains=job_title_or_company_name)

    # location
    if 'location' in request.GET:
        location = request.GET['location']
        if location:
            job_list = job_list.filter(location__icontains=location)

    # Job Type
    if 'job_type' in request.GET:
        job_type = request.GET['job_type']
        if job_type:
            job_list = job_list.filter(job_type__iexact=job_type)
        print(job_list)
    lst = job_data(job_title_or_company_name,location,job_type)
    print(lst)
    # job_title_or_company_name = request.GET.get('text')
    # location = request.GET.get('location')
    # job_type = request.GET.get('type')

    #     job_list = Job.objects.all()
    #     job_list = job_list.filter(
    #         Q(job_type__iexact=job_type) |
    #         Q(title__icontains=job_title_or_company_name) |
    #         Q(location__icontains=location)
    #     ).distinct()

    # job_list = Job.objects.filter(job_type__iexact=job_type) | Job.objects.filter(
    #     location__icontains=location) | Job.objects.filter(title__icontains=text) | Job.objects.filter(company_name__icontains=text)

    paginator = Paginator(lst, 8)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context = {

        'page_obj': page_obj,

    }
    return render(request, 'jobapp/result.html', context)


@login_required(login_url=reverse_lazy('account:login'))
@user_is_employee
def apply_job_view(request, id):

    form = JobApplyForm(request.POST or None)
    user = get_object_or_404(User, id=request.user.id)
    applicant = Applicant.objects.filter(user=user, job=id)

    if not applicant:
        if request.method == 'POST':

            if form.is_valid():
                instance = form.save(commit=False)
                instance.user = user
                instance.save()

                messages.success(
                    request, 'You have successfully applied for this job!')
                return redirect(reverse("jobapp:single-job", kwargs={
                    'id': id
                }))

        else:
            return redirect(reverse("jobapp:single-job", kwargs={
                'id': id
            }))

    else:

        messages.error(request, 'You already applied for the Job!')

        return redirect(reverse("jobapp:single-job", kwargs={
            'id': id
        }))


@login_required(login_url=reverse_lazy('account:login'))
def dashboard_view(request):
    """
    """
    jobs = []
    savedjobs = []
    appliedjobs = []
    total_applicants = {}

    savedjobs = Saved.objects.filter(user=request.user.id)
    appliedjobs = Applied.objects.filter(user=request.user.id)
    print(savedjobs)
    context = {
        'savedjobs': savedjobs,
        'appliedjobs':appliedjobs,
    }

    return render(request, 'jobapp/dashboard.html', context)


@login_required(login_url=reverse_lazy('account:login'))
@user_is_employer
def delete_job_view(request, id):

    job = get_object_or_404(Saved, id=id, user=request.user.id)

    if job:

        job.delete()
        messages.success(request, 'Your Job Post was successfully deleted!')

    return redirect('jobapp:dashboard')


@login_required(login_url=reverse_lazy('account:login'))
@user_is_employer
def make_complete_job_view(request, id):
    job = get_object_or_404(Job, id=id, user=request.user.id)

    if job:
        try:
            job.is_closed = True
            job.save()
            messages.success(request, 'Your Job was marked closed!')
        except:
            messages.success(request, 'Something went wrong !')
            
    return redirect('jobapp:dashboard')



@login_required(login_url=reverse_lazy('account:login'))
@user_is_employer
def all_applicants_view(request, id):

    all_applicants = Applicant.objects.filter(job=id)

    context = {

        'all_applicants': all_applicants
    }

    return render(request, 'jobapp/all-applicants.html', context)


@login_required(login_url=reverse_lazy('account:login'))
@user_is_employee
def delete_bookmark_view(request, id):

    job = get_object_or_404(BookmarkJob, id=id, user=request.user.id)

    if job:

        job.delete()
        messages.success(request, 'Saved Job was successfully deleted!')

    return redirect('jobapp:dashboard')


@login_required(login_url=reverse_lazy('account:login'))
@user_is_employer
def applicant_details_view(request, id):

    applicant = get_object_or_404(User, id=id)

    context = {

        'applicant': applicant
    }

    return render(request, 'jobapp/applicant-details.html', context)


@login_required(login_url=reverse_lazy('account:login'))
@user_is_employee
def job_bookmark_view(request, id):

    form = JobBookmarkForm(request.POST or None)

    user = get_object_or_404(User, id=request.user.id)
    applicant = BookmarkJob.objects.filter(user=request.user.id, job=id)

    if not applicant:
        if request.method == 'POST':

            if form.is_valid():
                instance = form.save(commit=False)
                instance.user = user
                instance.save()

                messages.success(
                    request, 'You have successfully save this job!')
                return redirect(reverse("jobapp:single-job", kwargs={
                    'id': id
                }))

        else:
            return redirect(reverse("jobapp:single-job", kwargs={
                'id': id
            }))

    else:
        messages.error(request, 'You already saved this Job!')

        return redirect(reverse("jobapp:single-job", kwargs={
            'id': id
        }))


@login_required(login_url=reverse_lazy('account:login'))
@user_is_employer
def job_edit_view(request, id=id):
    """
    Handle Employee Profile Update

    """

    job = get_object_or_404(Job, id=id)
    categories = Category.objects.all()
    form = JobEditForm(request.POST or None, instance=job)
    if form.is_valid():
        instance = form.save(commit=False)
        instance.save()
        # for save tags
        # form.save_m2m()
        messages.success(request, 'Your Job Post Was Successfully Updated!')
        return redirect(reverse("jobapp:single-job", kwargs={
            'id': instance.id
        }))
    context = {

        'form': form,
        'categories': categories
    }

    return render(request, 'jobapp/job-edit.html', context)
